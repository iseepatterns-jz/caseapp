#!/bin/bash

# RDS Deletion Protection Resolution Script
# Handles RDS instances with deletion protection that block CloudFormation stack deletion

set -euo pipefail

# Configuration
REGION="us-east-1"
STACK_NAME="CourtCaseManagementStack"

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

# Check if AWS CLI is configured
check_aws_cli() {
    log_info "Checking AWS CLI configuration..."
    
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS CLI is not configured or credentials are invalid."
        exit 1
    fi
    
    local caller_identity=$(aws sts get-caller-identity --query 'Account' --output text)
    log_success "AWS CLI configured for account: $caller_identity"
}

# Find RDS instances with deletion protection
find_protected_rds_instances() {
    log_info "Finding RDS instances with deletion protection..."
    
    local protected_instances
    protected_instances=$(aws rds describe-db-instances \
        --region "$REGION" \
        --query 'DBInstances[?DeletionProtection==`true` && contains(DBInstanceIdentifier, `courtcase`)].{InstanceId:DBInstanceIdentifier,Status:DBInstanceStatus,Engine:Engine,Class:DBInstanceClass}' \
        --output table)
    
    if [ -n "$protected_instances" ]; then
        log_warning "Found RDS instances with deletion protection enabled:"
        echo "$protected_instances"
        return 0
    else
        log_info "No RDS instances with deletion protection found"
        return 1
    fi
}

# Disable deletion protection for specific RDS instance
disable_deletion_protection() {
    local instance_id="$1"
    
    log_info "Disabling deletion protection for RDS instance: $instance_id"
    
    # Check current status
    local current_status
    current_status=$(aws rds describe-db-instances \
        --db-instance-identifier "$instance_id" \
        --region "$REGION" \
        --query 'DBInstances[0].DBInstanceStatus' \
        --output text)
    
    log_info "Current instance status: $current_status"
    
    if [ "$current_status" != "available" ]; then
        log_warning "Instance is not in 'available' state. Current state: $current_status"
        log_info "Waiting for instance to become available before modifying..."
        
        # Wait for instance to be available
        aws rds wait db-instance-available \
            --db-instance-identifier "$instance_id" \
            --region "$REGION" || {
                log_error "Timeout waiting for instance to become available"
                return 1
            }
    fi
    
    # Disable deletion protection
    log_info "Modifying RDS instance to disable deletion protection..."
    aws rds modify-db-instance \
        --db-instance-identifier "$instance_id" \
        --no-deletion-protection \
        --apply-immediately \
        --region "$REGION" || {
            log_error "Failed to disable deletion protection for $instance_id"
            return 1
        }
    
    log_success "Deletion protection disabled for $instance_id"
    
    # Wait for modification to complete
    log_info "Waiting for modification to complete..."
    aws rds wait db-instance-available \
        --db-instance-identifier "$instance_id" \
        --region "$REGION" || {
            log_warning "Timeout waiting for modification to complete, but continuing..."
        }
    
    # Verify deletion protection is disabled
    local protection_status
    protection_status=$(aws rds describe-db-instances \
        --db-instance-identifier "$instance_id" \
        --region "$REGION" \
        --query 'DBInstances[0].DeletionProtection' \
        --output text)
    
    if [ "$protection_status" = "False" ]; then
        log_success "✅ Deletion protection successfully disabled for $instance_id"
        return 0
    else
        log_error "❌ Failed to disable deletion protection for $instance_id"
        return 1
    fi
}

# Get all RDS instances associated with the stack
get_stack_rds_instances() {
    log_info "Finding RDS instances associated with CloudFormation stack: $STACK_NAME"
    
    # Try to get instances from stack resources first
    local stack_instances
    stack_instances=$(aws cloudformation describe-stack-resources \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'StackResources[?ResourceType==`AWS::RDS::DBInstance`].PhysicalResourceId' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$stack_instances" ]; then
        log_info "Found RDS instances in CloudFormation stack:"
        echo "$stack_instances"
        echo "$stack_instances"
    else
        # Fallback: find instances by naming pattern
        log_info "No stack found or no RDS resources in stack. Searching by naming pattern..."
        local pattern_instances
        pattern_instances=$(aws rds describe-db-instances \
            --region "$REGION" \
            --query 'DBInstances[?contains(DBInstanceIdentifier, `courtcase`)].DBInstanceIdentifier' \
            --output text)
        
        if [ -n "$pattern_instances" ]; then
            log_info "Found RDS instances matching naming pattern:"
            echo "$pattern_instances"
            echo "$pattern_instances"
        else
            log_info "No RDS instances found"
            echo ""
        fi
    fi
}

# Main execution function
main() {
    log_info "Starting RDS deletion protection resolution..."
    log_info "Stack: $STACK_NAME"
    log_info "Region: $REGION"
    echo
    
    # Pre-flight checks
    check_aws_cli
    echo
    
    # Find all RDS instances associated with the stack
    local rds_instances
    rds_instances=$(get_stack_rds_instances)
    
    if [ -z "$rds_instances" ]; then
        log_success "No RDS instances found. No action needed."
        exit 0
    fi
    
    echo
    
    # Check which instances have deletion protection
    if ! find_protected_rds_instances; then
        log_success "No RDS instances have deletion protection enabled. No action needed."
        exit 0
    fi
    
    echo
    log_warning "This script will disable deletion protection on RDS instances."
    log_warning "This is required to allow CloudFormation stack deletion."
    log_info "The instances themselves will NOT be deleted by this script."
    echo
    
    read -p "Do you want to continue and disable deletion protection? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Operation cancelled by user"
        exit 0
    fi
    
    echo
    log_info "Processing RDS instances..."
    
    # Process each instance
    local success_count=0
    local total_count=0
    
    for instance_id in $rds_instances; do
        total_count=$((total_count + 1))
        log_info "Processing instance: $instance_id"
        
        # Check if this instance has deletion protection
        local has_protection
        has_protection=$(aws rds describe-db-instances \
            --db-instance-identifier "$instance_id" \
            --region "$REGION" \
            --query 'DBInstances[0].DeletionProtection' \
            --output text 2>/dev/null || echo "False")
        
        if [ "$has_protection" = "True" ]; then
            log_info "Instance $instance_id has deletion protection enabled"
            
            if disable_deletion_protection "$instance_id"; then
                success_count=$((success_count + 1))
            fi
        else
            log_info "Instance $instance_id already has deletion protection disabled"
            success_count=$((success_count + 1))
        fi
        
        echo
    done
    
    # Summary
    log_info "Processing complete!"
    log_info "Successfully processed: $success_count/$total_count instances"
    
    if [ $success_count -eq $total_count ]; then
        log_success "✅ All RDS instances are now ready for CloudFormation stack deletion"
        log_info "You can now proceed with stack cleanup or redeployment"
    else
        log_warning "⚠️  Some instances could not be processed"
        log_info "Manual intervention may be required"
    fi
}

# Handle script interruption
trap 'log_error "Script interrupted by user"; exit 1' INT TERM

# Execute main function
main "$@"