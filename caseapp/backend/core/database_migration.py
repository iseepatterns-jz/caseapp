"""
Database migration automation for Court Case Management System
Handles database schema migrations safely before application startup
"""

import asyncio
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import structlog
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from core.database import get_db, validate_database_connection, engine
from core.config import settings

logger = structlog.get_logger()

class DatabaseMigrationManager:
    """Manages database migrations with safety checks and rollback capabilities"""
    
    def __init__(self):
        self.logger = logger.bind(service="database_migration")
        self.alembic_cfg = None
        self._setup_alembic_config()
    
    def _setup_alembic_config(self):
        """Setup Alembic configuration for migrations"""
        try:
            # Look for alembic.ini in the backend directory
            alembic_ini_path = Path(__file__).parent.parent / "alembic.ini"
            
            if alembic_ini_path.exists():
                self.alembic_cfg = Config(str(alembic_ini_path))
                # Override database URL from settings
                self.alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
                self.logger.info("Alembic configuration loaded", config_path=str(alembic_ini_path))
            else:
                self.logger.warning("Alembic configuration not found, migrations will be limited")
                
        except Exception as e:
            self.logger.error("Failed to setup Alembic configuration", error=str(e))
    
    async def check_database_exists(self) -> bool:
        """
        Check if the database exists and is accessible
        
        Returns:
            bool: True if database exists and is accessible
        """
        try:
            return await validate_database_connection()
        except Exception as e:
            self.logger.error("Database existence check failed", error=str(e))
            return False
    
    async def get_current_schema_version(self) -> Optional[str]:
        """
        Get the current database schema version
        
        Returns:
            Optional[str]: Current schema version or None if not versioned
        """
        try:
            async for db in get_db():
                # Check if alembic_version table exists
                result = await db.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'alembic_version'
                    )
                """))
                
                table_exists = result.scalar()
                
                if table_exists:
                    # Get current version
                    version_result = await db.execute(text("SELECT version_num FROM alembic_version"))
                    version_row = version_result.fetchone()
                    
                    if version_row:
                        return version_row[0]
                
                return None
                
        except Exception as e:
            self.logger.error("Failed to get current schema version", error=str(e))
            return None
    
    async def get_pending_migrations(self) -> List[str]:
        """
        Get list of pending migrations that need to be applied
        
        Returns:
            List[str]: List of pending migration revision IDs
        """
        if not self.alembic_cfg:
            return []
        
        try:
            script = ScriptDirectory.from_config(self.alembic_cfg)
            
            # Get current version
            current_version = await self.get_current_schema_version()
            
            # Get all revisions
            revisions = list(script.walk_revisions())
            
            if current_version is None:
                # No version table, all migrations are pending
                return [rev.revision for rev in reversed(revisions)]
            
            # Find pending migrations
            pending = []
            found_current = False
            
            for rev in reversed(revisions):
                if rev.revision == current_version:
                    found_current = True
                    continue
                
                if found_current:
                    pending.append(rev.revision)
            
            return pending
            
        except Exception as e:
            self.logger.error("Failed to get pending migrations", error=str(e))
            return []
    
    async def create_initial_tables(self) -> bool:
        """
        Create initial database tables if they don't exist
        
        Returns:
            bool: True if tables were created successfully
        """
        try:
            from models import Base  # Import all models
            
            # Create all tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            self.logger.info("Initial database tables created successfully")
            return True
            
        except Exception as e:
            self.logger.error("Failed to create initial tables", error=str(e))
            return False
    
    async def run_migrations(self, target_revision: str = "head") -> Dict[str, Any]:
        """
        Run database migrations to the specified target revision
        
        Args:
            target_revision: Target revision to migrate to (default: "head")
            
        Returns:
            Dict[str, Any]: Migration result with status and details
        """
        if not self.alembic_cfg:
            return {
                "status": "error",
                "message": "Alembic configuration not available",
                "migrations_applied": []
            }
        
        try:
            # Get pending migrations before running
            pending_migrations = await self.get_pending_migrations()
            
            if not pending_migrations:
                return {
                    "status": "success",
                    "message": "No pending migrations to apply",
                    "migrations_applied": []
                }
            
            self.logger.info("Starting database migrations", 
                           pending_count=len(pending_migrations),
                           target_revision=target_revision)
            
            # Run migrations
            command.upgrade(self.alembic_cfg, target_revision)
            
            # Verify migrations were applied
            new_version = await self.get_current_schema_version()
            
            self.logger.info("Database migrations completed successfully",
                           new_version=new_version,
                           migrations_applied=pending_migrations)
            
            return {
                "status": "success",
                "message": f"Successfully applied {len(pending_migrations)} migrations",
                "migrations_applied": pending_migrations,
                "new_version": new_version
            }
            
        except Exception as e:
            self.logger.error("Database migration failed", error=str(e))
            return {
                "status": "error",
                "message": f"Migration failed: {str(e)}",
                "migrations_applied": []
            }
    
    async def rollback_migration(self, target_revision: str) -> Dict[str, Any]:
        """
        Rollback database to a specific revision
        
        Args:
            target_revision: Target revision to rollback to
            
        Returns:
            Dict[str, Any]: Rollback result with status and details
        """
        if not self.alembic_cfg:
            return {
                "status": "error",
                "message": "Alembic configuration not available"
            }
        
        try:
            current_version = await self.get_current_schema_version()
            
            self.logger.info("Starting database rollback",
                           current_version=current_version,
                           target_revision=target_revision)
            
            # Perform rollback
            command.downgrade(self.alembic_cfg, target_revision)
            
            # Verify rollback
            new_version = await self.get_current_schema_version()
            
            self.logger.info("Database rollback completed successfully",
                           old_version=current_version,
                           new_version=new_version)
            
            return {
                "status": "success",
                "message": f"Successfully rolled back from {current_version} to {new_version}",
                "old_version": current_version,
                "new_version": new_version
            }
            
        except Exception as e:
            self.logger.error("Database rollback failed", error=str(e))
            return {
                "status": "error",
                "message": f"Rollback failed: {str(e)}"
            }
    
    async def validate_schema_integrity(self) -> Dict[str, Any]:
        """
        Validate database schema integrity
        
        Returns:
            Dict[str, Any]: Validation result with status and details
        """
        try:
            async for db in get_db():
                # Check for required tables
                required_tables = [
                    'users', 'cases', 'documents', 'timeline_events', 
                    'media_files', 'forensic_analyses'
                ]
                
                missing_tables = []
                existing_tables = []
                
                for table_name in required_tables:
                    result = await db.execute(text(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = '{table_name}'
                        )
                    """))
                    
                    if result.scalar():
                        existing_tables.append(table_name)
                    else:
                        missing_tables.append(table_name)
                
                # Check for foreign key constraints
                fk_result = await db.execute(text("""
                    SELECT COUNT(*) as fk_count
                    FROM information_schema.table_constraints 
                    WHERE constraint_type = 'FOREIGN KEY'
                    AND table_schema = 'public'
                """))
                
                fk_count = fk_result.scalar()
                
                # Determine overall status
                if missing_tables:
                    status = "incomplete"
                    message = f"Schema incomplete: missing tables {missing_tables}"
                else:
                    status = "valid"
                    message = "Schema integrity validated successfully"
                
                return {
                    "status": status,
                    "message": message,
                    "existing_tables": existing_tables,
                    "missing_tables": missing_tables,
                    "foreign_key_count": fk_count,
                    "schema_version": await self.get_current_schema_version()
                }
                
        except Exception as e:
            self.logger.error("Schema integrity validation failed", error=str(e))
            return {
                "status": "error",
                "message": f"Validation failed: {str(e)}"
            }
    
    async def safe_migration_startup(self) -> Dict[str, Any]:
        """
        Perform safe database migration during application startup
        
        Returns:
            Dict[str, Any]: Startup migration result
        """
        self.logger.info("Starting safe database migration for application startup")
        
        try:
            # Step 1: Check database connectivity
            if not await self.check_database_exists():
                return {
                    "status": "error",
                    "message": "Database is not accessible",
                    "step": "connectivity_check"
                }
            
            # Step 2: Validate current schema
            schema_validation = await self.validate_schema_integrity()
            
            # Step 3: Check for pending migrations
            pending_migrations = await self.get_pending_migrations()
            
            if not pending_migrations:
                self.logger.info("No pending migrations, database is up to date")
                return {
                    "status": "success",
                    "message": "Database is up to date, no migrations needed",
                    "schema_validation": schema_validation
                }
            
            # Step 4: Apply pending migrations
            migration_result = await self.run_migrations()
            
            if migration_result["status"] == "success":
                # Step 5: Final validation
                final_validation = await self.validate_schema_integrity()
                
                return {
                    "status": "success",
                    "message": "Database migration completed successfully",
                    "migration_result": migration_result,
                    "final_validation": final_validation
                }
            else:
                return {
                    "status": "error",
                    "message": "Migration failed during startup",
                    "migration_result": migration_result
                }
                
        except Exception as e:
            self.logger.error("Safe migration startup failed", error=str(e))
            return {
                "status": "error",
                "message": f"Startup migration failed: {str(e)}"
            }

# Global migration manager instance
migration_manager = DatabaseMigrationManager()

async def run_startup_migrations() -> bool:
    """
    Run database migrations during application startup
    
    Returns:
        bool: True if migrations completed successfully
    """
    result = await migration_manager.safe_migration_startup()
    return result["status"] == "success"

async def get_migration_status() -> Dict[str, Any]:
    """
    Get current migration status for health checks
    
    Returns:
        Dict[str, Any]: Migration status information
    """
    try:
        current_version = await migration_manager.get_current_schema_version()
        pending_migrations = await migration_manager.get_pending_migrations()
        schema_validation = await migration_manager.validate_schema_integrity()
        
        return {
            "current_version": current_version,
            "pending_migrations": pending_migrations,
            "pending_count": len(pending_migrations),
            "schema_status": schema_validation["status"],
            "database_accessible": await migration_manager.check_database_exists()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }