#!/bin/bash

# Deployment Coordinator Script
# Manages deployment queuing and coordination to prevent concurrent deployments

set -euo pipefail

# Configuration
REGION="${AWS_REGION:-us-east-1}"
REGISTRY_DIR="${REGISTRY_DIR:-.deployment-registry}"
REGISTRY_FILE="$REGISTRY_DIR/deployments.json"

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

# Initialize registry directory and file
init_registry() {
    if [ ! -d "$REGISTRY_DIR" ]; then
        mkdir -p "$REGISTRY_DIR"
        log_info "Created registry directory: $REGISTRY_DIR"
    fi
    
    if [ ! -f "$REGISTRY_FILE" ]; then
        echo '{"deployments":[]}' > "$REGISTRY_FILE"
        log_info "Initialized registry file: $REGISTRY_FILE"
    fi
}

# Read registry with file locking
read_registry() {
    init_registry
    
    # Use flock for file locking (wait up to 10 seconds)
    if command -v flock &> /dev/null; then
        flock -w 10 "$REGISTRY_FILE" cat "$REGISTRY_FILE"
    else
        cat "$REGISTRY_FILE"
    fi
}

# Write registry with file locking
write_registry() {
    local content="$1"
    init_registry
    
    # Use flock for file locking
    if command -v flock &> /dev/null; then
        echo "$content" | flock -w 10 "$REGISTRY_FILE" tee "$REGISTRY_FILE" > /dev/null
    else
        echo "$content" > "$REGISTRY_FILE"
    fi
}

# Check if deployment can proceed
can_deploy() {
    local environment="$1"
    local stack_name="${2:-CourtCaseManagementStack}"
    
    if [ "$environment" = "staging" ]; then
        stack_name="CourtCaseManagementStack-Staging"
    fi
    
    log_info "Checking if deployment can proceed for environment: $environment"
    
    # Try to use registry first
    if [ -f "$REGISTRY_FILE" ] && [ -r "$REGISTRY_FILE" ]; then
        # Registry is available, use it
        log_info "Using deployment registry for coordination"
    else
        # Registry unavailable, fall back to CloudFormation only
        log_warning "Registry unavailable, falling back to CloudFormation-only coordination"
        bash "$(dirname "$0")/registry-fallback.sh" can_deploy "$environment"
        return $?
    fi
    
    # Check CloudFormation stack status
    local stack_status
    stack_status=$(AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "STACK_NOT_FOUND")
    
    # Check for active deployment states
    case "$stack_status" in
        CREATE_IN_PROGRESS|UPDATE_IN_PROGRESS|ROLLBACK_IN_PROGRESS|UPDATE_ROLLBACK_IN_PROGRESS|UPDATE_COMPLETE_CLEANUP_IN_PROGRESS)
            log_warning "Active deployment detected in CloudFormation"
            
            # Get deployment details
            local stack_info
            stack_info=$(AWS_PAGER="" aws cloudformation describe-stacks \
                --stack-name "$stack_name" \
                --region "$REGION" \
                --query 'Stacks[0]' \
                --output json 2>/dev/null || echo "{}")
            
            local creation_time=$(echo "$stack_info" | jq -r '.CreationTime // "UNKNOWN"')
            local last_updated=$(echo "$stack_info" | jq -r '.LastUpdatedTime // .CreationTime // "UNKNOWN"')
            
            # Calculate elapsed time
            local start_time="$creation_time"
            if [ "$last_updated" != "UNKNOWN" ] && [ "$last_updated" != "$creation_time" ]; then
                start_time="$last_updated"
            fi
            
            local elapsed_minutes=0
            if [ "$start_time" != "UNKNOWN" ]; then
                # Parse ISO 8601 timestamp (works on both macOS and Linux)
                local start_epoch=$(date -d "$start_time" "+%s" 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S%z" "$start_time" "+%s" 2>/dev/null || echo "0")
                local now_epoch=$(date "+%s")
                if [ "$start_epoch" != "0" ]; then
                    elapsed_minutes=$(( (now_epoch - start_epoch) / 60 ))
                fi
            fi
            
            # Estimate remaining time (average deployment is 25 minutes)
            local estimated_remaining=$((25 - elapsed_minutes))
            if [ $estimated_remaining -lt 5 ]; then
                estimated_remaining=5
            fi
            
            # Return JSON response
            cat <<EOF
{
  "can_deploy": false,
  "reason": "ACTIVE_DEPLOYMENT_IN_PROGRESS",
  "active_deployment": {
    "stack_name": "$stack_name",
    "status": "$stack_status",
    "started_at": "$start_time",
    "elapsed_minutes": $elapsed_minutes,
    "estimated_remaining_minutes": $estimated_remaining
  }
}
EOF
            return 1
            ;;
        STACK_NOT_FOUND)
            log_success "No existing stack - ready for fresh deployment"
            echo '{"can_deploy": true, "reason": "NO_STACK_EXISTS"}'
            return 0
            ;;
        *)
            log_success "Stack exists but not actively deploying (status: $stack_status)"
            echo '{"can_deploy": true, "reason": "STACK_IDLE"}'
            return 0
            ;;
    esac
}

# Register a deployment
register_deployment() {
    local correlation_id="$1"
    local workflow_run_id="$2"
    local environment="$3"
    local stack_name="${4:-CourtCaseManagementStack}"
    
    if [ "$environment" = "staging" ]; then
        stack_name="CourtCaseManagementStack-Staging"
    fi
    
    log_info "Registering deployment: $correlation_id"
    
    # Read current registry
    local registry=$(read_registry)
    
    # Check for duplicate registration
    local existing=$(echo "$registry" | jq -r ".deployments[] | select(.correlation_id == \"$correlation_id\") | .correlation_id")
    if [ -n "$existing" ]; then
        log_warning "Deployment already registered: $correlation_id"
        return 0
    fi
    
    # Create new deployment entry
    local timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    local new_deployment=$(cat <<EOF
{
  "correlation_id": "$correlation_id",
  "workflow_run_id": "$workflow_run_id",
  "environment": "$environment",
  "stack_name": "$stack_name",
  "status": "IN_PROGRESS",
  "started_at": "$timestamp",
  "updated_at": "$timestamp"
}
EOF
)
    
    # Add to registry
    local updated_registry=$(echo "$registry" | jq ".deployments += [$new_deployment]")
    write_registry "$updated_registry"
    
    log_success "Deployment registered successfully"
}

# Wait for active deployment to complete
wait_for_deployment() {
    local environment="$1"
    local max_wait_minutes="${2:-30}"
    local stack_name="${3:-CourtCaseManagementStack}"
    
    if [ "$environment" = "staging" ]; then
        stack_name="CourtCaseManagementStack-Staging"
    fi
    
    log_info "Waiting for active deployment to complete (max wait: ${max_wait_minutes} minutes)"
    
    local check_interval=30  # Check every 30 seconds
    local max_wait_seconds=$((max_wait_minutes * 60))
    local elapsed=0
    
    while [ $elapsed -lt $max_wait_seconds ]; do
        # Check stack status
        local stack_status
        stack_status=$(AWS_PAGER="" aws cloudformation describe-stacks \
            --stack-name "$stack_name" \
            --region "$REGION" \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null || echo "STACK_NOT_FOUND")
        
        # Check if deployment is complete
        case "$stack_status" in
            CREATE_COMPLETE|UPDATE_COMPLETE|ROLLBACK_COMPLETE|UPDATE_ROLLBACK_COMPLETE)
                log_success "Active deployment completed with status: $stack_status"
                return 0
                ;;
            CREATE_FAILED|UPDATE_FAILED|ROLLBACK_FAILED|UPDATE_ROLLBACK_FAILED|DELETE_COMPLETE|DELETE_FAILED)
                log_warning "Active deployment ended with status: $stack_status"
                return 0
                ;;
            STACK_NOT_FOUND)
                log_success "Stack no longer exists - deployment complete"
                return 0
                ;;
            *)
                # Still in progress
                log_info "Deployment still in progress (status: $stack_status) - elapsed: ${elapsed}s"
                sleep $check_interval
                elapsed=$((elapsed + check_interval))
                ;;
        esac
    done
    
    log_error "Timeout waiting for deployment after ${max_wait_minutes} minutes"
    return 1
}

# Cleanup deployment registration
cleanup_deployment() {
    local correlation_id="$1"
    
    log_info "Cleaning up deployment registration: $correlation_id"
    
    # Read current registry
    local registry=$(read_registry)
    
    # Remove deployment from registry
    local updated_registry=$(echo "$registry" | jq ".deployments |= map(select(.correlation_id != \"$correlation_id\"))")
    write_registry "$updated_registry"
    
    log_success "Deployment registration cleaned up"
}

# Get active deployment details
get_active_deployment() {
    local environment="$1"
    
    # Read registry
    local registry=$(read_registry)
    
    # Find active deployment for environment
    local active=$(echo "$registry" | jq -r ".deployments[] | select(.environment == \"$environment\" and .status == \"IN_PROGRESS\")")
    
    if [ -n "$active" ]; then
        echo "$active"
        return 0
    else
        echo "{}"
        return 1
    fi
}

# Show usage
usage() {
    cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  can_deploy <environment> [stack_name]
      Check if deployment can proceed for the given environment
      
  register <correlation_id> <workflow_run_id> <environment> [stack_name]
      Register a new deployment
      
  wait <environment> [max_wait_minutes] [stack_name]
      Wait for active deployment to complete
      
  cleanup <correlation_id>
      Remove deployment from registry
      
  get_active <environment>
      Get details of active deployment for environment

Examples:
  $0 can_deploy production
  $0 register 20260114-123456-abc123 12345 production
  $0 wait production 30
  $0 cleanup 20260114-123456-abc123
  $0 get_active production
EOF
}

# Main command dispatcher
main() {
    if [ $# -lt 1 ]; then
        usage
        exit 1
    fi
    
    local command="$1"
    shift
    
    case "$command" in
        can_deploy)
            if [ $# -lt 1 ]; then
                log_error "Missing required argument: environment"
                usage
                exit 1
            fi
            can_deploy "$@"
            ;;
        register)
            if [ $# -lt 3 ]; then
                log_error "Missing required arguments"
                usage
                exit 1
            fi
            register_deployment "$@"
            ;;
        wait)
            if [ $# -lt 1 ]; then
                log_error "Missing required argument: environment"
                usage
                exit 1
            fi
            wait_for_deployment "$@"
            ;;
        cleanup)
            if [ $# -lt 1 ]; then
                log_error "Missing required argument: correlation_id"
                usage
                exit 1
            fi
            cleanup_deployment "$@"
            ;;
        get_active)
            if [ $# -lt 1 ]; then
                log_error "Missing required argument: environment"
                usage
                exit 1
            fi
            get_active_deployment "$@"
            ;;
        *)
            log_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"
