"""
Database configuration and session management with connection pooling and retry logic
"""

import asyncio
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy import text, event
from sqlalchemy.exc import DisconnectionError, OperationalError
import structlog
import time

from core.config import settings

logger = structlog.get_logger()

class DatabaseConnectionManager:
    """Enhanced database connection manager with pooling and retry logic"""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self._connection_validated = False
        self._last_validation_time = 0
        self._validation_interval = 300  # 5 minutes
        
    def create_engine(self):
        """Create database engine with optimized connection pooling"""
        if self.engine is not None:
            return self.engine
            
        # Convert PostgreSQL URL to asyncpg format
        database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        
        # Create engine with connection pooling and retry logic
        # Prepare engine arguments
        engine_args = {
            "echo": settings.DEBUG,
            "echo_pool": settings.DEBUG,
            "execution_options": {
                "isolation_level": "READ_COMMITTED"
            },
            "connect_args": {
                "server_settings": {
                    "application_name": "court_case_management",
                    "jit": "off"
                },
                "command_timeout": 60,
            }
        }
        
        # Configure pooling based on environment
        if settings.TESTING:
            # Use NullPool for testing to avoid connection persistence across event loops
            engine_args["poolclass"] = NullPool
        else:
            # Production pool configuration
            engine_args.update({
                "pool_size": 10,
                "max_overflow": 20,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
                "pool_timeout": 30,
            })
            
        # Create engine
        self.engine = create_async_engine(database_url, **engine_args)
        
        # Add connection event listeners for monitoring
        @event.listens_for(self.engine.sync_engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            logger.info("Database connection established", 
                       connection_id=id(dbapi_connection))
        
        @event.listens_for(self.engine.sync_engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            logger.debug("Database connection checked out from pool",
                        connection_id=id(dbapi_connection))
        
        @event.listens_for(self.engine.sync_engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            logger.debug("Database connection returned to pool",
                        connection_id=id(dbapi_connection))
        
        return self.engine
    
    def create_session_factory(self):
        """Create session factory with proper configuration"""
        if self.session_factory is not None:
            return self.session_factory
            
        if self.engine is None:
            self.create_engine()
            
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
        
        return self.session_factory
    
    async def validate_connection(self, force: bool = False) -> bool:
        """
        Validate database connection with caching to avoid excessive checks
        
        Args:
            force: Force validation even if recently validated
            
        Returns:
            bool: True if connection is valid
        """
        current_time = time.time()
        
        # Use cached validation if recent and not forced
        if (not force and 
            self._connection_validated and 
            (current_time - self._last_validation_time) < self._validation_interval):
            return True
        
        try:
            if self.engine is None:
                self.create_engine()
            
            # Test connection with simple query
            async with self.engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 as test"))
                row = result.fetchone()
                
                if row and row.test == 1:
                    self._connection_validated = True
                    self._last_validation_time = current_time
                    logger.info("Database connection validation successful")
                    return True
                else:
                    logger.error("Database connection validation failed: unexpected result")
                    self._connection_validated = False
                    return False
                    
        except Exception as e:
            logger.error("Database connection validation failed", error=str(e))
            self._connection_validated = False
            return False
    
    async def get_session_with_retry(self, max_retries: int = 3, retry_delay: float = 1.0) -> AsyncSession:
        """
        Get database session with retry logic for transient failures
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
            
        Returns:
            AsyncSession: Database session
            
        Raises:
            Exception: If all retry attempts fail
        """
        if self.session_factory is None:
            self.create_session_factory()
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                session = self.session_factory()
                
                # Test the session with a simple query
                await session.execute(text("SELECT 1"))
                
                logger.debug("Database session created successfully", attempt=attempt + 1)
                return session
                
            except (DisconnectionError, OperationalError, ConnectionError) as e:
                last_exception = e
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        "Database connection attempt failed, retrying",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay,
                        error=str(e)
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "All database connection attempts failed",
                        attempts=max_retries + 1,
                        error=str(e)
                    )
            except Exception as e:
                # Non-retryable error
                logger.error("Database session creation failed with non-retryable error", error=str(e))
                raise
        
        # If we get here, all retries failed
        raise last_exception or Exception("Failed to create database session after retries")

# Global database connection manager
db_manager = DatabaseConnectionManager()

# Create engine and session factory
engine = db_manager.create_engine()
AsyncSessionLocal = db_manager.create_session_factory()

# Create declarative base
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Enhanced database session dependency with retry logic and proper error handling
    
    Yields:
        AsyncSession: Database session with automatic cleanup
    """
    session = None
    try:
        # Get session with retry logic
        session = await db_manager.get_session_with_retry()
        
        logger.debug("Database session started")
        yield session
        
        # Commit any pending transactions
        await session.commit()
        logger.debug("Database session committed successfully")
        
    except Exception as e:
        logger.error("Database session error", error=str(e), error_type=type(e).__name__)
        
        if session:
            try:
                await session.rollback()
                logger.info("Database session rolled back due to error")
            except Exception as rollback_error:
                logger.error("Failed to rollback database session", error=str(rollback_error))
        
        raise
    finally:
        if session:
            try:
                await session.close()
                logger.debug("Database session closed")
            except Exception as close_error:
                logger.error("Failed to close database session", error=str(close_error))

async def validate_database_connection() -> bool:
    """
    Validate database connection for health checks
    
    Returns:
        bool: True if database is accessible and responsive
    """
    return await db_manager.validate_connection()

async def get_database_info() -> dict:
    """
    Get database connection information for diagnostics
    
    Returns:
        dict: Database connection details
    """
    try:
        if engine is None:
            return {"status": "not_initialized", "error": "Engine not created"}
        
        # Get pool status
        pool = engine.pool
        try:
            pool_info = {
                "pool_size": getattr(pool, 'size', lambda: 'unknown')(),
                "checked_in": getattr(pool, 'checkedin', lambda: 'unknown')(),
                "checked_out": getattr(pool, 'checkedout', lambda: 'unknown')(),
                "overflow": getattr(pool, 'overflow', lambda: 'unknown')(),
                "invalid": getattr(pool, 'invalid', lambda: 'unknown')()
            }
        except Exception:
            # Fallback for async pool that may not have all methods
            pool_info = {
                "pool_type": str(type(pool).__name__),
                "status": "active"
            }
        
        # Test connection
        connection_valid = await db_manager.validate_connection()
        
        return {
            "status": "healthy" if connection_valid else "unhealthy",
            "connection_valid": connection_valid,
            "pool_info": pool_info,
            "database_url": settings.DATABASE_URL.split('@')[0] + '@***',  # Hide credentials
            "last_validation": db_manager._last_validation_time
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }