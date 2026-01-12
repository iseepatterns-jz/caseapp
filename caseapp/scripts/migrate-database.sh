#!/bin/bash

# Database Migration Script for Court Case Management System
# This script handles database migrations safely with rollback capabilities

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if database is accessible
check_database_connection() {
    log_info "Checking database connection..."
    
    cd "$BACKEND_DIR"
    
    if python3 -c "
import asyncio
import sys
sys.path.append('.')

async def test_connection():
    try:
        from core.database import validate_database_connection
        return await validate_database_connection()
    except Exception as e:
        print(f'Connection error: {e}')
        return False

result = asyncio.run(test_connection())
sys.exit(0 if result else 1)
    "; then
        log_success "Database connection successful"
        return 0
    else
        log_error "Database connection failed"
        return 1
    fi
}

# Function to get current migration version
get_current_version() {
    cd "$BACKEND_DIR"
    
    python3 -c "
import asyncio
import sys
sys.path.append('.')

async def get_version():
    try:
        from core.database_migration import migration_manager
        version = await migration_manager.get_current_schema_version()
        print(version or 'None')
    except Exception as e:
        print('Error')

asyncio.run(get_version())
    "
}

# Function to get pending migrations
get_pending_migrations() {
    cd "$BACKEND_DIR"
    
    python3 -c "
import asyncio
import sys
sys.path.append('.')

async def get_pending():
    try:
        from core.database_migration import migration_manager
        pending = await migration_manager.get_pending_migrations()
        print(len(pending))
    except Exception as e:
        print('0')

asyncio.run(get_pending())
    "
}

# Function to run migrations
run_migrations() {
    local target_revision="${1:-head}"
    
    log_info "Running database migrations to revision: $target_revision"
    
    cd "$BACKEND_DIR"
    
    # Check if alembic is available
    if ! python3 -c "import alembic" 2>/dev/null; then
        log_error "Alembic is not installed. Please install it with: pip install alembic"
        return 1
    fi
    
    # Run migrations using our migration manager
    python3 -c "
import asyncio
import sys
sys.path.append('.')

async def run_migration():
    try:
        from core.database_migration import migration_manager
        result = await migration_manager.run_migrations('$target_revision')
        
        if result['status'] == 'success':
            print('Migration completed successfully')
            print(f'Applied migrations: {result[\"migrations_applied\"]}')
            return True
        else:
            print(f'Migration failed: {result[\"message\"]}')
            return False
    except Exception as e:
        print(f'Migration error: {e}')
        return False

success = asyncio.run(run_migration())
sys.exit(0 if success else 1)
    "
    
    if [ $? -eq 0 ]; then
        log_success "Database migrations completed successfully"
        return 0
    else
        log_error "Database migrations failed"
        return 1
    fi
}

# Function to rollback migrations
rollback_migrations() {
    local target_revision="$1"
    
    log_warning "Rolling back database to revision: $target_revision"
    
    cd "$BACKEND_DIR"
    
    python3 -c "
import asyncio
import sys
sys.path.append('.')

async def rollback_migration():
    try:
        from core.database_migration import migration_manager
        result = await migration_manager.rollback_migration('$target_revision')
        
        if result['status'] == 'success':
            print('Rollback completed successfully')
            return True
        else:
            print(f'Rollback failed: {result[\"message\"]}')
            return False
    except Exception as e:
        print(f'Rollback error: {e}')
        return False

success = asyncio.run(rollback_migration())
sys.exit(0 if success else 1)
    "
    
    if [ $? -eq 0 ]; then
        log_success "Database rollback completed successfully"
        return 0
    else
        log_error "Database rollback failed"
        return 1
    fi
}

# Function to validate schema integrity
validate_schema() {
    log_info "Validating database schema integrity..."
    
    cd "$BACKEND_DIR"
    
    python3 -c "
import asyncio
import sys
sys.path.append('.')

async def validate():
    try:
        from core.database_migration import migration_manager
        result = await migration_manager.validate_schema_integrity()
        
        print(f'Schema status: {result[\"status\"]}')
        print(f'Message: {result[\"message\"]}')
        
        if 'existing_tables' in result:
            print(f'Existing tables: {len(result[\"existing_tables\"])}')
        
        if 'missing_tables' in result and result['missing_tables']:
            print(f'Missing tables: {result[\"missing_tables\"]}')
        
        return result['status'] in ['valid', 'incomplete']
    except Exception as e:
        print(f'Validation error: {e}')
        return False

success = asyncio.run(validate())
sys.exit(0 if success else 1)
    "
    
    if [ $? -eq 0 ]; then
        log_success "Schema validation completed"
        return 0
    else
        log_error "Schema validation failed"
        return 1
    fi
}

# Function to show migration status
show_status() {
    log_info "Database Migration Status"
    echo "=========================="
    
    if ! check_database_connection; then
        log_error "Cannot connect to database"
        return 1
    fi
    
    local current_version
    current_version=$(get_current_version)
    echo "Current version: $current_version"
    
    local pending_count
    pending_count=$(get_pending_migrations)
    echo "Pending migrations: $pending_count"
    
    if [ "$pending_count" -gt 0 ]; then
        log_warning "There are $pending_count pending migrations"
    else
        log_success "Database is up to date"
    fi
    
    validate_schema
}

# Function to create a new migration
create_migration() {
    local message="$1"
    
    log_info "Creating new migration: $message"
    
    cd "$BACKEND_DIR"
    
    if ! command -v alembic &> /dev/null; then
        log_error "Alembic command not found. Please ensure alembic is installed and in PATH"
        return 1
    fi
    
    alembic revision --autogenerate -m "$message"
    
    if [ $? -eq 0 ]; then
        log_success "Migration created successfully"
        return 0
    else
        log_error "Failed to create migration"
        return 1
    fi
}

# Function to show help
show_help() {
    echo "Database Migration Script for Court Case Management System"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  status                    Show current migration status"
    echo "  migrate [revision]        Run migrations (default: head)"
    echo "  rollback <revision>       Rollback to specific revision"
    echo "  validate                  Validate schema integrity"
    echo "  create <message>          Create new migration"
    echo "  help                      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 status                 # Show migration status"
    echo "  $0 migrate                # Run all pending migrations"
    echo "  $0 migrate abc123         # Migrate to specific revision"
    echo "  $0 rollback def456        # Rollback to revision def456"
    echo "  $0 create 'Add user table' # Create new migration"
    echo ""
    echo "Environment Variables:"
    echo "  DATABASE_URL              Database connection string"
    echo ""
}

# Main script logic
main() {
    local command="${1:-help}"
    
    case "$command" in
        "status")
            show_status
            ;;
        "migrate")
            local revision="${2:-head}"
            if check_database_connection; then
                run_migrations "$revision"
            else
                log_error "Cannot connect to database. Please check your DATABASE_URL"
                exit 1
            fi
            ;;
        "rollback")
            if [ -z "${2:-}" ]; then
                log_error "Rollback requires a target revision"
                show_help
                exit 1
            fi
            if check_database_connection; then
                rollback_migrations "$2"
            else
                log_error "Cannot connect to database. Please check your DATABASE_URL"
                exit 1
            fi
            ;;
        "validate")
            if check_database_connection; then
                validate_schema
            else
                log_error "Cannot connect to database. Please check your DATABASE_URL"
                exit 1
            fi
            ;;
        "create")
            if [ -z "${2:-}" ]; then
                log_error "Create requires a migration message"
                show_help
                exit 1
            fi
            create_migration "$2"
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"