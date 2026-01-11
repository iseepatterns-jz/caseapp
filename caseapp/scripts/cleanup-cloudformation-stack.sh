#!/bin/bash

# CloudFormation Stack Cleanup Automation Script
# Handles failed stack cleanup with proper dependency resolution

set -euo pipefail

# Configuration
STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"
MAX_WAIT_TIME=1800  # 30 minutes
POLL_INTERVAL=30    # 30 seconds

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

# Check if stack exists and get its status
get_stack_status() {
    local stack_status
    stack_status=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "STACK_NOT_FOUND")
    
    echo "$stack_status"
}

# Get failed resources from stack
get_failed_resources() {
    log_info "Identifying failed resources..."
    
    aws cloudformation describe-stack-resources \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'StackResources[?ResourceStatus==`DELETE_FAILED`].{LogicalId:LogicalResourceId,PhysicalId:PhysicalResourceId,Type:ResourceType}' \
        --output table
}

# Force delete RDS instances that are blocking cleanup
cleanup_rds_instances() {
    log_info "Checking for RDS instances blocking cleanup..."
    
    local db_instances
    db_instances=$(aws rds describe-db-instances \
        --region "$REGION" \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `courtcase`)].DBInstanceIdentifier' \
        --output text)
    
    if [ -n "$db_instances" ]; then
        log_warning "Found RDS instances that may be blocking cleanup:"
        echo "$db_instances"
        
        read -p "Do you want to delete these RDS instances? This will permanently delete the databases. (y/N): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            for db_instance in $db_instances; do
                log_info "Deleting RDS instance: $db_instance"
                
                # Delete without final snapshot for cleanup purposes
                aws rds delete-db-instance \
                    --db-instance-identifier "$db_instance" \
                    --skip-final-snapshot \
                    --delete-automated-backups \
                    --region "$REGION" || log_warning "Failed to delete $db_instance"
                
                log_info "Waiting for RDS instance $db_instance to be deleted..."
                aws rds wait db-instance-deleted \
                    --db-instance-identifier "$db_instance" \
                    --region "$REGION" || log_warning "Timeout waiting for $db_instance deletion"
            done
            
            log_success "RDS instances cleanup completed"
        else
            log_warning "Skipping RDS instance deletion. Manual cleanup may be required."
        fi
    else
        log_info "No RDS instances found blocking cleanup"
    fi
}

# Force delete security groups with dependencies
cleanup_security_groups() {
    log_info "Checking for security groups blocking cleanup..."
    
    # Get security groups from failed stack resources
    local security_groups
    security_groups=$(aws cloudformation describe-stack-resources \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'StackResources[?ResourceStatus==`DELETE_FAILED` && ResourceType==`AWS::EC2::SecurityGroup`].PhysicalResourceId' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$security_groups" ]; then
        log_warning "Found security groups that may have dependencies:"
        echo "$security_groups"
        
        for sg_id in $security_groups; do
            log_info "Checking dependencies for security group: $sg_id"
            
            # Check for network interfaces using this security group
            local enis
            enis=$(aws ec2 describe-network-interfaces \
                --filters "Name=group-id,Values=$sg_id" \
                --query 'NetworkInterfaces[].NetworkInterfaceId' \
                --output text \
                --region "$REGION" 2>/dev/null || echo "")
            
            if [ -n "$enis" ]; then
                log_warning "Security group $sg_id has dependent network interfaces: $enis"
                log_info "These will be cleaned up when associated resources are deleted"
            fi
        done
    else
        log_info "No security groups found blocking cleanup"
    fi
}

# Attempt to continue stack deletion
continue_stack_deletion() {
    local stack_status
    stack_status=$(get_stack_status)
    
    log_info "Current stack status: $stack_status"
    
    case "$stack_status" in
        "ROLLBACK_FAILED")
            log_info "Stack is in ROLLBACK_FAILED state. Attempting to continue rollback..."
            
            # Try to continue the rollback by skipping failed resources
            aws cloudformation continue-update-rollback \
                --stack-name "$STACK_NAME" \
                --region "$REGION" \
                --resources-to-skip DatabaseSecurityGroup7319C0F6 DatabaseSubnetGroup \
                2>/dev/null || {
                    log_warning "Continue rollback failed. Attempting direct stack deletion..."
                    delete_stack_force
                }
            ;;
        "DELETE_FAILED")
            log_info "Stack is in DELETE_FAILED state. Attempting direct deletion..."
            delete_stack_force
            ;;
        "STACK_NOT_FOUND")
            log_success "Stack does not exist. No cleanup needed."
            return 0
            ;;
        *)
            log_info "Stack is in $stack_status state. Attempting deletion..."
            aws cloudformation delete-stack \
                --stack-name "$STACK_NAME" \
                --region "$REGION"
            ;;
    esac
    
    # Wait for stack deletion to complete
    wait_for_stack_deletion
}

# Force delete stack by retaining problematic resources
delete_stack_force() {
    log_info "Attempting force deletion by retaining problematic resources..."
    
    # Get list of failed resources to retain
    local retain_resources
    retain_resources=$(aws cloudformation describe-stack-resources \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'StackResources[?ResourceStatus==`DELETE_FAILED`].LogicalResourceId' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$retain_resources" ]; then
        log_info "Retaining problematic resources: $retain_resources"
        
        # Convert space-separated list to comma-separated for AWS CLI
        local retain_list
        retain_list=$(echo "$retain_resources" | tr ' ' ',')
        
        aws cloudformation delete-stack \
            --stack-name "$STACK_NAME" \
            --retain-resources $retain_list \
            --region "$REGION" || {
                log_error "Force deletion with retained resources failed"
                return 1
            }
    else
        # Try regular deletion
        aws cloudformation delete-stack \
            --stack-name "$STACK_NAME" \
            --region "$REGION" || {
                log_error "Regular stack deletion failed"
                return 1
            }
    fi
}

# Wait for stack deletion to complete
wait_for_stack_deletion() {
    log_info "Waiting for stack deletion to complete..."
    
    local elapsed=0
    local stack_status
    
    while [ $elapsed -lt $MAX_WAIT_TIME ]; do
        stack_status=$(get_stack_status)
        
        case "$stack_status" in
            "STACK_NOT_FOUND")
                log_success "Stack successfully deleted!"
                return 0
                ;;
            "DELETE_COMPLETE")
                log_success "Stack deletion completed!"
                return 0
                ;;
            "DELETE_FAILED")
                log_error "Stack deletion failed. Manual intervention required."
                get_failed_resources
                return 1
                ;;
            "DELETE_IN_PROGRESS")
                log_info "Stack deletion in progress... (${elapsed}s elapsed)"
                ;;
            *)
                log_info "Stack status: $stack_status (${elapsed}s elapsed)"
                ;;
        esac
        
        sleep $POLL_INTERVAL
        elapsed=$((elapsed + POLL_INTERVAL))
    done
    
    log_error "Timeout waiting for stack deletion after ${MAX_WAIT_TIME}s"
    return 1
}

# Clean up orphaned resources manually
cleanup_orphaned_resources() {
    log_info "Checking for orphaned resources that need manual cleanup..."
    
    # Check for orphaned RDS subnet groups
    local orphaned_subnet_groups
    orphaned_subnet_groups=$(aws rds describe-db-subnet-groups \
        --region "$REGION" \
        --query 'DBSubnetGroups[?contains(DBSubnetGroupName, `courtcase`)].DBSubnetGroupName' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$orphaned_subnet_groups" ]; then
        log_warning "Found orphaned RDS subnet groups:"
        echo "$orphaned_subnet_groups"
        
        read -p "Do you want to delete these orphaned subnet groups? (y/N): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            for subnet_group in $orphaned_subnet_groups; do
                log_info "Deleting orphaned subnet group: $subnet_group"
                aws rds delete-db-subnet-group \
                    --db-subnet-group-name "$subnet_group" \
                    --region "$REGION" || log_warning "Failed to delete $subnet_group"
            done
        fi
    fi
    
    # Check for orphaned security groups
    local orphaned_security_groups
    orphaned_security_groups=$(aws ec2 describe-security-groups \
        --region "$REGION" \
        --filters "Name=group-name,Values=*CourtCase*" \
        --query 'SecurityGroups[?GroupName!=`default`].GroupId' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$orphaned_security_groups" ]; then
        log_warning "Found potentially orphaned security groups:"
        echo "$orphaned_security_groups"
        
        log_info "Please manually verify and delete these if they are no longer needed"
        log_info "Command: aws ec2 delete-security-group --group-id <group-id> --region $REGION"
    fi
}

# Validate cleanup completion
validate_cleanup() {
    log_info "Validating cleanup completion..."
    
    local stack_status
    stack_status=$(get_stack_status)
    
    if [ "$stack_status" = "STACK_NOT_FOUND" ]; then
        log_success "✅ CloudFormation stack successfully removed"
    else
        log_error "❌ CloudFormation stack still exists with status: $stack_status"
        return 1
    fi
    
    # Check for remaining resources
    local remaining_rds
    remaining_rds=$(aws rds describe-db-instances \
        --region "$REGION" \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `courtcase`)].DBInstanceIdentifier' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$remaining_rds" ]; then
        log_warning "⚠️  Remaining RDS instances: $remaining_rds"
    else
        log_success "✅ No remaining RDS instances found"
    fi
    
    log_success "Cleanup validation completed"
}

# Main execution
main() {
    log_info "Starting CloudFormation stack cleanup for: $STACK_NAME"
    log_info "Region: $REGION"
    echo
    
    # Pre-flight checks
    check_aws_cli
    
    local stack_status
    stack_status=$(get_stack_status)
    
    if [ "$stack_status" = "STACK_NOT_FOUND" ]; then
        log_success "Stack does not exist. No cleanup needed."
        exit 0
    fi
    
    log_info "Current stack status: $stack_status"
    echo
    
    # Show current failed resources
    get_failed_resources
    echo
    
    # Confirm cleanup
    log_warning "This script will attempt to clean up the failed CloudFormation stack."
    log_warning "This may involve deleting AWS resources permanently."
    echo
    read -p "Do you want to continue? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cleanup cancelled by user"
        exit 0
    fi
    
    echo
    log_info "Starting cleanup process..."
    
    # Step 1: Clean up RDS instances blocking subnet group deletion
    cleanup_rds_instances
    echo
    
    # Step 2: Analyze security group dependencies
    cleanup_security_groups
    echo
    
    # Step 3: Attempt to continue/complete stack deletion
    if continue_stack_deletion; then
        log_success "Stack deletion completed successfully"
    else
        log_warning "Stack deletion encountered issues. Checking for orphaned resources..."
        cleanup_orphaned_resources
    fi
    
    echo
    
    # Step 4: Validate cleanup
    validate_cleanup
    
    echo
    log_success "CloudFormation stack cleanup process completed!"
    log_info "You can now attempt a fresh deployment."
}

# Handle script interruption
trap 'log_error "Script interrupted by user"; exit 1' INT TERM

# Execute main function
main "$@"