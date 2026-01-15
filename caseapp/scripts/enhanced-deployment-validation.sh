#!/bin/bash

# Enhanced Deployment Validation Script
# Handles resource conflicts and provides automated resolution options

set -euo pipefail

# Configuration
REGION="us-east-1"
STACK_NAME="CourtCaseManagementStack"
DOCKER_USERNAME="${DOCKER_USERNAME:-}"

# Generate correlation ID for this deployment
CORRELATION_ID="${CORRELATION_ID:-$(date +%Y%m%d-%H%M%S)-$(openssl rand -hex 4)}"
export CORRELATION_ID

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Enhanced logging functions with correlation ID and timestamps
log_info() {
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo -e "${BLUE}[INFO]${NC} [$timestamp] [ID:$CORRELATION_ID] $1"
    
    # Also log to structured log file if available
    if [ -n "${DEPLOYMENT_LOG_FILE:-}" ]; then
        echo "{\"timestamp\":\"$timestamp\",\"level\":\"INFO\",\"correlation_id\":\"$CORRELATION_ID\",\"message\":\"$1\"}" >> "$DEPLOYMENT_LOG_FILE"
    fi
}

log_success() {
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo -e "${GREEN}[SUCCESS]${NC} [$timestamp] [ID:$CORRELATION_ID] $1"
    
    if [ -n "${DEPLOYMENT_LOG_FILE:-}" ]; then
        echo "{\"timestamp\":\"$timestamp\",\"level\":\"SUCCESS\",\"correlation_id\":\"$CORRELATION_ID\",\"message\":\"$1\"}" >> "$DEPLOYMENT_LOG_FILE"
    fi
}

log_warning() {
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo -e "${YELLOW}[WARNING]${NC} [$timestamp] [ID:$CORRELATION_ID] $1"
    
    if [ -n "${DEPLOYMENT_LOG_FILE:-}" ]; then
        echo "{\"timestamp\":\"$timestamp\",\"level\":\"WARNING\",\"correlation_id\":\"$CORRELATION_ID\",\"message\":\"$1\"}" >> "$DEPLOYMENT_LOG_FILE"
    fi
}

log_error() {
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo -e "${RED}[ERROR]${NC} [$timestamp] [ID:$CORRELATION_ID] $1"
    
    if [ -n "${DEPLOYMENT_LOG_FILE:-}" ]; then
        echo "{\"timestamp\":\"$timestamp\",\"level\":\"ERROR\",\"correlation_id\":\"$CORRELATION_ID\",\"message\":\"$1\"}" >> "$DEPLOYMENT_LOG_FILE"
    fi
}

# Log deployment phase transitions
log_phase() {
    local phase="$1"
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo -e "${BLUE}[PHASE]${NC} [$timestamp] [ID:$CORRELATION_ID] === $phase ==="
    
    if [ -n "${DEPLOYMENT_LOG_FILE:-}" ]; then
        echo "{\"timestamp\":\"$timestamp\",\"level\":\"PHASE\",\"correlation_id\":\"$CORRELATION_ID\",\"phase\":\"$phase\"}" >> "$DEPLOYMENT_LOG_FILE"
    fi
}

# Check if we're running in CI environment
is_ci_environment() {
    [ "${CI:-false}" = "true" ] || [ "${GITHUB_ACTIONS:-false}" = "true" ]
}

# Check AWS CLI configuration
check_aws_cli() {
    log_info "Checking AWS CLI configuration..."
    
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed"
        return 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS CLI is not configured or credentials are invalid"
        return 1
    fi
    
    log_success "AWS CLI configured successfully"
    return 0
}

# Check Docker image accessibility
check_docker_images() {
    log_info "Checking Docker image accessibility..."
    
    if [ -z "$DOCKER_USERNAME" ]; then
        log_warning "DOCKER_USERNAME not set, skipping Docker image validation"
        return 0
    fi
    
    local backend_image="$DOCKER_USERNAME/court-case-backend:latest"
    local media_image="$DOCKER_USERNAME/court-case-media:latest"
    
    # Check backend image
    if docker manifest inspect "$backend_image" > /dev/null 2>&1; then
        log_success "Backend image accessible: $backend_image"
    else
        log_error "Backend image not accessible: $backend_image"
        return 1
    fi
    
    # Check media image
    if docker manifest inspect "$media_image" > /dev/null 2>&1; then
        log_success "Media image accessible: $media_image"
    else
        log_error "Media image not accessible: $media_image"
        return 1
    fi
    
    return 0
}

# Get detailed deployment status
get_deployment_status() {
    local stack_name="$1"
    local region="${2:-$REGION}"
    
    # Get stack information
    local stack_info
    stack_info=$(AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$region" \
        --query 'Stacks[0]' \
        --output json 2>/dev/null || echo "{}")
    
    if [ "$stack_info" = "{}" ]; then
        echo "STACK_NOT_FOUND"
        return 1
    fi
    
    # Extract key information
    local status=$(echo "$stack_info" | jq -r '.StackStatus // "UNKNOWN"')
    local creation_time=$(echo "$stack_info" | jq -r '.CreationTime // "UNKNOWN"')
    local last_updated=$(echo "$stack_info" | jq -r '.LastUpdatedTime // .CreationTime // "UNKNOWN"')
    
    # Get recent stack events (last 5)
    local recent_events
    recent_events=$(AWS_PAGER="" aws cloudformation describe-stack-events \
        --stack-name "$stack_name" \
        --region "$region" \
        --max-items 5 \
        --query 'StackEvents[*].[Timestamp,ResourceType,ResourceStatus,ResourceStatusReason]' \
        --output text 2>/dev/null || echo "")
    
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
    
    # Return structured information
    echo "STATUS:$status"
    echo "STARTED:$start_time"
    echo "ELAPSED_MINUTES:$elapsed_minutes"
    echo "RECENT_EVENTS:$recent_events"
}

# Estimate deployment completion time
estimate_completion_time() {
    local stack_status="$1"
    local elapsed_minutes="$2"
    
    # Historical averages (in minutes)
    # These are based on typical deployment times
    local avg_create_time=25
    local avg_update_time=20
    local avg_rollback_time=15
    
    local total_expected=0
    case "$stack_status" in
        CREATE_IN_PROGRESS)
            total_expected=$avg_create_time
            ;;
        UPDATE_IN_PROGRESS)
            total_expected=$avg_update_time
            ;;
        ROLLBACK_IN_PROGRESS|UPDATE_ROLLBACK_IN_PROGRESS)
            total_expected=$avg_rollback_time
            ;;
        *)
            echo "0"
            return
            ;;
    esac
    
    # Calculate remaining time
    local remaining=$((total_expected - elapsed_minutes))
    if [ $remaining -lt 0 ]; then
        remaining=5  # At least 5 minutes if we're over estimate
    fi
    
    echo "$remaining"
}

# Generate AWS Console link
get_console_link() {
    local stack_name="$1"
    local region="${2:-$REGION}"
    
    # URL encode the stack name
    local encoded_stack_name=$(echo "$stack_name" | sed 's/ /%20/g')
    
    echo "https://console.aws.amazon.com/cloudformation/home?region=${region}#/stacks/stackinfo?stackId=${encoded_stack_name}"
}

# Check if deployment is currently in progress with detailed reporting
check_deployment_in_progress() {
    log_info "Checking if deployment is currently in progress..."
    
    local stack_status
    stack_status=$(AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "STACK_NOT_FOUND")
    
    # Check for active deployment states
    case "$stack_status" in
        CREATE_IN_PROGRESS|UPDATE_IN_PROGRESS|ROLLBACK_IN_PROGRESS|UPDATE_ROLLBACK_IN_PROGRESS|UPDATE_COMPLETE_CLEANUP_IN_PROGRESS)
            log_error "Deployment is currently in progress with status: $stack_status"
            echo
            
            # Get detailed status information
            log_info "Fetching detailed deployment status..."
            local status_info=$(get_deployment_status "$STACK_NAME" "$REGION")
            
            local started=$(echo "$status_info" | grep "^STARTED:" | cut -d: -f2-)
            local elapsed=$(echo "$status_info" | grep "^ELAPSED_MINUTES:" | cut -d: -f2)
            local estimated_remaining=$(estimate_completion_time "$stack_status" "$elapsed")
            
            log_info "Active Deployment Details:"
            log_info "  Status: $stack_status"
            log_info "  Started: $started"
            log_info "  Elapsed Time: ${elapsed} minutes"
            log_info "  Estimated Remaining: ${estimated_remaining} minutes"
            echo
            
            # Show recent events
            log_info "Recent Stack Events:"
            local events=$(echo "$status_info" | grep "^RECENT_EVENTS:" | cut -d: -f2-)
            if [ -n "$events" ]; then
                echo "$events" | head -5 | while IFS=$'\t' read -r timestamp resource_type status reason; do
                    log_info "  [$timestamp] $resource_type: $status"
                done
            fi
            echo
            
            # Provide AWS Console link
            local console_link=$(get_console_link "$STACK_NAME" "$REGION")
            log_info "Monitor deployment in AWS Console:"
            log_info "  $console_link"
            echo
            
            log_error "❌ Cannot proceed - deployment is already in progress"
            log_error "Wait for the current deployment to complete before starting a new one"
            
            return 0  # Return 0 to indicate deployment IS in progress
            ;;
        STACK_NOT_FOUND)
            log_success "No active deployment detected"
            return 1  # Return 1 to indicate deployment is NOT in progress
            ;;
        *)
            log_info "Stack exists with status: $stack_status (not actively deploying)"
            return 1  # Return 1 to indicate deployment is NOT in progress
            ;;
    esac
}

# Check for existing CloudFormation stack
check_existing_stack() {
    log_info "Checking for existing CloudFormation stack..."
    
    local stack_status
    stack_status=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "STACK_NOT_FOUND")
    
    if [ "$stack_status" = "STACK_NOT_FOUND" ]; then
        log_success "No existing stack found - ready for fresh deployment"
        return 0
    else
        log_warning "Existing stack found with status: $stack_status"
        return 1
    fi
}

# Check for RDS instances with deletion protection
check_rds_deletion_protection() {
    log_info "Checking for RDS instances with deletion protection..."
    
    local protected_instances
    protected_instances=$(aws rds describe-db-instances \
        --region "$REGION" \
        --query 'DBInstances[?DeletionProtection==`true` && contains(DBInstanceIdentifier, `courtcase`)].DBInstanceIdentifier' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$protected_instances" ]; then
        log_warning "Found RDS instances with deletion protection:"
        echo "$protected_instances"
        return 1
    else
        log_success "No RDS instances with deletion protection found"
        return 0
    fi
}

# Check for RDS instances that are currently deleting
check_rds_deleting() {
    log_info "Checking for RDS instances that are currently deleting..."
    
    local deleting_instances
    deleting_instances=$(aws rds describe-db-instances \
        --region "$REGION" \
        --query 'DBInstances[?DBInstanceStatus==`deleting` && contains(DBInstanceIdentifier, `courtcase`)].DBInstanceIdentifier' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$deleting_instances" ]; then
        log_warning "Found RDS instances currently deleting:"
        echo "$deleting_instances"
        return 1
    else
        log_success "No RDS instances currently deleting"
        return 0
    fi
}

# Wait for RDS deletion to complete
wait_for_rds_deletion() {
    log_info "Waiting for RDS deletion to complete..."
    
    local deleting_instances
    deleting_instances=$(aws rds describe-db-instances \
        --region "$REGION" \
        --query 'DBInstances[?DBInstanceStatus==`deleting` && contains(DBInstanceIdentifier, `courtcase`)].DBInstanceIdentifier' \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$deleting_instances" ]; then
        log_success "No RDS instances to wait for"
        return 0
    fi
    
    log_info "Waiting for RDS instances to finish deleting: $deleting_instances"
    log_info "This may take 10-15 minutes..."
    
    local max_wait=1200  # 20 minutes max wait
    local elapsed=0
    local check_interval=30
    
    while [ $elapsed -lt $max_wait ]; do
        deleting_instances=$(aws rds describe-db-instances \
            --region "$REGION" \
            --query 'DBInstances[?DBInstanceStatus==`deleting` && contains(DBInstanceIdentifier, `courtcase`)].DBInstanceIdentifier' \
            --output text 2>/dev/null || echo "")
        
        if [ -z "$deleting_instances" ]; then
            log_success "All RDS instances have finished deleting"
            return 0
        fi
        
        log_info "Still waiting... (${elapsed}s elapsed)"
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
    done
    
    log_error "Timeout waiting for RDS deletion after ${max_wait}s"
    return 1
}

# Check for resource conflicts
check_resource_conflicts() {
    log_info "Checking for resource conflicts..."
    
    local conflicts=0
    
    # Check for existing stack
    if ! check_existing_stack; then
        conflicts=$((conflicts + 1))
    fi
    
    # Check for RDS deletion protection
    if ! check_rds_deletion_protection; then
        conflicts=$((conflicts + 1))
    fi
    
    return $conflicts
}

# Resolve RDS deletion protection automatically
resolve_rds_deletion_protection() {
    log_info "Resolving RDS deletion protection..."
    
    if [ -f "scripts/resolve-rds-deletion-protection.sh" ]; then
        # In CI environment, run automatically with 'y' response
        if is_ci_environment; then
            log_info "Running in CI environment - automatically resolving RDS deletion protection"
            echo "y" | ./scripts/resolve-rds-deletion-protection.sh
        else
            # In interactive environment, let user decide
            ./scripts/resolve-rds-deletion-protection.sh
        fi
    else
        log_error "RDS deletion protection resolution script not found"
        return 1
    fi
}

# Resolve stack conflicts automatically
resolve_stack_conflicts() {
    log_info "Resolving CloudFormation stack conflicts..."
    
    if [ -f "scripts/cleanup-cloudformation-stack.sh" ]; then
        # In CI environment, run automatically with 'y' response
        if is_ci_environment; then
            log_info "Running in CI environment - automatically cleaning up existing stack"
            echo "y" | ./scripts/cleanup-cloudformation-stack.sh
        else
            # In interactive environment, let user decide
            ./scripts/cleanup-cloudformation-stack.sh
        fi
    else
        log_error "CloudFormation cleanup script not found"
        return 1
    fi
}

# Main validation function
main() {
    log_phase "Enhanced Deployment Validation Started"
    log_info "Stack: $STACK_NAME"
    log_info "Region: $REGION"
    log_info "Correlation ID: $CORRELATION_ID"
    echo
    
    # CRITICAL: Check if deployment is already in progress FIRST
    log_phase "Deployment State Check"
    if check_deployment_in_progress; then
        log_error "❌ Cannot proceed - deployment is already in progress"
        log_error "Wait for the current deployment to complete before starting a new one"
        exit 2
    fi
    
    log_phase "Basic Infrastructure Checks"
    # Basic checks
    if ! check_aws_cli; then
        log_error "AWS CLI check failed"
        exit 2
    fi
    
    if ! check_docker_images; then
        log_error "Docker image check failed"
        exit 2
    fi
    
    echo
    
    # Check if RDS instances are currently deleting
    log_phase "RDS Deletion Status Check"
    if ! check_rds_deleting; then
        log_warning "RDS instances are currently deleting"
        
        # In CI environment or if AUTO_RESOLVE is set, wait for deletion
        if is_ci_environment || [ "${AUTO_RESOLVE:-false}" = "true" ]; then
            log_info "Waiting for RDS deletion to complete before proceeding..."
            if ! wait_for_rds_deletion; then
                log_error "Failed to wait for RDS deletion"
                exit 1
            fi
        else
            log_error "RDS instances are deleting. Please wait for deletion to complete."
            log_info "Run with AUTO_RESOLVE=true to wait automatically"
            exit 1
        fi
    fi
    
    echo
    
    log_phase "Resource Conflict Detection"
    # Check for resource conflicts
    local conflict_count
    if ! check_resource_conflicts; then
        conflict_count=$?
        log_warning "Found $conflict_count resource conflict(s)"
        
        # In CI environment or if AUTO_RESOLVE is set, attempt automatic resolution
        if is_ci_environment || [ "${AUTO_RESOLVE:-false}" = "true" ]; then
            log_phase "Automatic Conflict Resolution"
            log_info "Attempting automatic conflict resolution..."
            
            # Resolve RDS deletion protection first
            if ! check_rds_deletion_protection; then
                log_info "Resolving RDS deletion protection conflicts..."
                if ! resolve_rds_deletion_protection; then
                    log_error "Failed to resolve RDS deletion protection"
                    exit 1
                fi
            fi
            
            # Then resolve stack conflicts
            if ! check_existing_stack; then
                log_info "Resolving CloudFormation stack conflicts..."
                if ! resolve_stack_conflicts; then
                    log_error "Failed to resolve stack conflicts"
                    exit 1
                fi
            fi
            
            # Re-check after resolution
            log_phase "Post-Resolution Validation"
            log_info "Re-validating after conflict resolution..."
            if check_resource_conflicts; then
                log_success "All conflicts resolved successfully"
            else
                log_error "Some conflicts remain after resolution attempt"
                exit 1
            fi
        else
            # Interactive mode - provide guidance
            log_warning "Resource conflicts detected. Manual resolution required:"
            echo
            log_info "To resolve automatically, run with AUTO_RESOLVE=true"
            log_info "Or run the following scripts manually:"
            
            if ! check_rds_deletion_protection; then
                log_info "  1. ./scripts/resolve-rds-deletion-protection.sh"
            fi
            
            if ! check_existing_stack; then
                log_info "  2. ./scripts/cleanup-cloudformation-stack.sh"
            fi
            
            exit 1
        fi
    else
        log_success "No resource conflicts detected"
    fi
    
    echo
    log_phase "Validation Complete"
    log_success "✅ All deployment validation checks passed"
    log_info "Deployment can proceed safely"
    
    return 0
}

# Handle script interruption
trap 'log_error "Script interrupted by user"; exit 1' INT TERM

# Execute main function
main "$@"
