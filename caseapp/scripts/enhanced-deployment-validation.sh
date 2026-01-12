#!/bin/bash

# Enhanced Deployment Validation Script
# Handles resource conflicts and provides automated resolution options

set -euo pipefail

# Configuration
REGION="us-east-1"
STACK_NAME="CourtCaseManagementStack"
DOCKER_USERNAME="${DOCKER_USERNAME:-}"

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
    log_info "Starting enhanced deployment validation..."
    log_info "Stack: $STACK_NAME"
    log_info "Region: $REGION"
    echo
    
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
    
    # Check for resource conflicts
    local conflict_count
    if ! check_resource_conflicts; then
        conflict_count=$?
        log_warning "Found $conflict_count resource conflict(s)"
        
        # In CI environment or if AUTO_RESOLVE is set, attempt automatic resolution
        if is_ci_environment || [ "${AUTO_RESOLVE:-false}" = "true" ]; then
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
    log_success "✅ All deployment validation checks passed"
    log_info "Deployment can proceed safely"
    
    return 0
}

# Handle script interruption
trap 'log_error "Script interrupted by user"; exit 1' INT TERM

# Execute main function
main "$@"