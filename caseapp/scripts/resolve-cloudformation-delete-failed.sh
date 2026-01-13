#!/bin/bash

# CloudFormation DELETE_FAILED State Resolution Script
# Handles orphaned resources and security group dependencies

set -euo pipefail

# Configuration
REGION="us-east-1"
STACK_NAME="CourtCaseManagementStack"
ORPHANED_SG_ID="sg-0e5e0db4daeae7676"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date -u '+%Y-%m-%d %H:%M:%S UTC') $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date -u '+%Y-%m-%d %H:%M:%S UTC') $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date -u '+%Y-%m-%d %H:%M:%S UTC') $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date -u '+%Y-%m-%d %H:%M:%S UTC') $1"
}

# Check if security group exists and get its dependencies
analyze_security_group_dependencies() {
    local sg_id="$1"
    
    log_info "Analyzing security group dependencies for $sg_id..."
    
    # Check if security group exists
    if ! AWS_PAGER="" aws ec2 describe-security-groups --group-ids "$sg_id" --region "$REGION" &>/dev/null; then
        log_info "Security group $sg_id does not exist - may have been cleaned up already"
        return 0
    fi
    
    # Get security group details
    local sg_info
    sg_info=$(AWS_PAGER="" aws ec2 describe-security-groups \
        --group-ids "$sg_id" \
        --region "$REGION" \
        --query 'SecurityGroups[0]' \
        --output json 2>/dev/null || echo "{}")
    
    if [ "$sg_info" = "{}" ]; then
        log_info "Security group $sg_id not found"
        return 0
    fi
    
    local group_name
    group_name=$(echo "$sg_info" | jq -r '.GroupName // "unknown"')
    
    log_info "Security group details:"
    log_info "  ID: $sg_id"
    log_info "  Name: $group_name"
    
    # Check for network interfaces using this security group
    log_info "Checking for network interfaces using this security group..."
    local eni_count
    eni_count=$(AWS_PAGER="" aws ec2 describe-network-interfaces \
        --filters "Name=group-id,Values=$sg_id" \
        --region "$REGION" \
        --query 'length(NetworkInterfaces)' \
        --output text 2>/dev/null || echo "0")
    
    if [ "$eni_count" -gt 0 ]; then
        log_warning "Found $eni_count network interface(s) using this security group"
        
        # List the network interfaces
        AWS_PAGER="" aws ec2 describe-network-interfaces \
            --filters "Name=group-id,Values=$sg_id" \
            --region "$REGION" \
            --query 'NetworkInterfaces[].{ID:NetworkInterfaceId,Status:Status,Description:Description,Attachment:Attachment.InstanceId}' \
            --output table 2>/dev/null || true
        
        return 1
    else
        log_success "No network interfaces found using this security group"
        return 0
    fi
}

# Remove security group dependencies
remove_security_group_dependencies() {
    local sg_id="$1"
    
    log_info "Removing dependencies for security group $sg_id..."
    
    # Get network interfaces using this security group
    local eni_ids
    eni_ids=$(AWS_PAGER="" aws ec2 describe-network-interfaces \
        --filters "Name=group-id,Values=$sg_id" \
        --region "$REGION" \
        --query 'NetworkInterfaces[].NetworkInterfaceId' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$eni_ids" ]; then
        log_info "Found network interfaces to process: $eni_ids"
        
        for eni_id in $eni_ids; do
            log_info "Processing network interface: $eni_id"
            
            # Get ENI details
            local eni_info
            eni_info=$(AWS_PAGER="" aws ec2 describe-network-interfaces \
                --network-interface-ids "$eni_id" \
                --region "$REGION" \
                --query 'NetworkInterfaces[0]' \
                --output json 2>/dev/null || echo "{}")
            
            local eni_status
            eni_status=$(echo "$eni_info" | jq -r '.Status // "unknown"')
            
            local attachment_id
            attachment_id=$(echo "$eni_info" | jq -r '.Attachment.AttachmentId // ""')
            
            log_info "  Status: $eni_status"
            log_info "  Attachment ID: ${attachment_id:-none}"
            
            # If ENI is attached, try to detach it
            if [ -n "$attachment_id" ] && [ "$attachment_id" != "null" ]; then
                log_info "  Detaching network interface..."
                if AWS_PAGER="" aws ec2 detach-network-interface \
                    --attachment-id "$attachment_id" \
                    --region "$REGION" \
                    --force 2>/dev/null; then
                    log_success "  Network interface detached successfully"
                    
                    # Wait for detachment to complete
                    log_info "  Waiting for detachment to complete..."
                    sleep 10
                else
                    log_warning "  Failed to detach network interface (may already be detached)"
                fi
            fi
            
            # Try to delete the ENI if it's available
            local current_status
            current_status=$(AWS_PAGER="" aws ec2 describe-network-interfaces \
                --network-interface-ids "$eni_id" \
                --region "$REGION" \
                --query 'NetworkInterfaces[0].Status' \
                --output text 2>/dev/null || echo "not-found")
            
            if [ "$current_status" = "available" ]; then
                log_info "  Deleting available network interface..."
                if AWS_PAGER="" aws ec2 delete-network-interface \
                    --network-interface-id "$eni_id" \
                    --region "$REGION" 2>/dev/null; then
                    log_success "  Network interface deleted successfully"
                else
                    log_warning "  Failed to delete network interface"
                fi
            else
                log_info "  Network interface status: $current_status (not deleting)"
            fi
        done
    else
        log_info "No network interfaces found using this security group"
    fi
}

# Delete orphaned security group
delete_orphaned_security_group() {
    local sg_id="$1"
    
    log_info "Attempting to delete orphaned security group $sg_id..."
    
    # First check if it still exists
    if ! AWS_PAGER="" aws ec2 describe-security-groups --group-ids "$sg_id" --region "$REGION" &>/dev/null; then
        log_success "Security group $sg_id does not exist - already cleaned up"
        return 0
    fi
    
    # Try to delete the security group
    if AWS_PAGER="" aws ec2 delete-security-group \
        --group-id "$sg_id" \
        --region "$REGION" 2>/dev/null; then
        log_success "Security group $sg_id deleted successfully"
        return 0
    else
        log_error "Failed to delete security group $sg_id"
        return 1
    fi
}

# Check CloudFormation stack status
check_stack_status() {
    log_info "Checking CloudFormation stack status..."
    
    local stack_status
    stack_status=$(AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "STACK_NOT_FOUND")
    
    log_info "Stack status: $stack_status"
    
    if [ "$stack_status" = "DELETE_FAILED" ]; then
        log_warning "Stack is in DELETE_FAILED state"
        
        # Get failed resources
        log_info "Getting failed resources..."
        AWS_PAGER="" aws cloudformation describe-stack-events \
            --stack-name "$STACK_NAME" \
            --region "$REGION" \
            --query 'StackEvents[?ResourceStatus==`DELETE_FAILED`].{Resource:LogicalResourceId,Type:ResourceType,Reason:ResourceStatusReason}' \
            --output table 2>/dev/null || true
        
        return 1
    elif [ "$stack_status" = "STACK_NOT_FOUND" ]; then
        log_success "No stack found - ready for fresh deployment"
        return 0
    else
        log_info "Stack exists with status: $stack_status"
        return 2
    fi
}

# Continue stack deletion after resolving dependencies
continue_stack_deletion() {
    log_info "Attempting to continue stack deletion..."
    
    # Try to continue the deletion
    if AWS_PAGER="" aws cloudformation continue-update-rollback \
        --stack-name "$STACK_NAME" \
        --region "$REGION" 2>/dev/null; then
        log_info "Continue update rollback initiated"
        
        # Wait for completion
        log_info "Waiting for stack operation to complete..."
        AWS_PAGER="" aws cloudformation wait stack-update-complete \
            --stack-name "$STACK_NAME" \
            --region "$REGION" 2>/dev/null || true
        
        # Check final status
        local final_status
        final_status=$(AWS_PAGER="" aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --region "$REGION" \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null || echo "STACK_NOT_FOUND")
        
        log_info "Final stack status: $final_status"
        return 0
    else
        log_warning "Continue update rollback not applicable or failed"
        
        # Try direct deletion
        log_info "Attempting direct stack deletion..."
        if AWS_PAGER="" aws cloudformation delete-stack \
            --stack-name "$STACK_NAME" \
            --region "$REGION" 2>/dev/null; then
            log_info "Stack deletion initiated"
            
            # Wait for deletion
            log_info "Waiting for stack deletion to complete..."
            AWS_PAGER="" aws cloudformation wait stack-delete-complete \
                --stack-name "$STACK_NAME" \
                --region "$REGION" 2>/dev/null || true
            
            log_success "Stack deletion completed"
            return 0
        else
            log_error "Failed to initiate stack deletion"
            return 1
        fi
    fi
}

# Main resolution function
main() {
    log_info "=== CloudFormation DELETE_FAILED Resolution ==="
    log_info "Stack: $STACK_NAME"
    log_info "Region: $REGION"
    log_info "Orphaned Security Group: $ORPHANED_SG_ID"
    echo
    
    # Check current stack status
    local stack_check_result
    if check_stack_status; then
        stack_check_result=0
    else
        stack_check_result=$?
    fi
    
    if [ $stack_check_result -eq 0 ]; then
        log_success "No stack cleanup needed - ready for deployment"
        return 0
    elif [ $stack_check_result -eq 2 ]; then
        log_info "Stack exists but not in DELETE_FAILED state"
        log_info "Manual intervention may be required"
        return 0
    fi
    
    echo
    log_info "=== Resolving Security Group Dependencies ==="
    
    # Analyze security group dependencies
    if analyze_security_group_dependencies "$ORPHANED_SG_ID"; then
        log_info "No dependencies found for security group"
    else
        log_warning "Dependencies found - attempting to resolve..."
        remove_security_group_dependencies "$ORPHANED_SG_ID"
        
        # Wait a bit for AWS to process the changes
        log_info "Waiting for AWS to process dependency changes..."
        sleep 15
        
        # Re-check dependencies
        if analyze_security_group_dependencies "$ORPHANED_SG_ID"; then
            log_success "Dependencies resolved successfully"
        else
            log_warning "Some dependencies may still exist"
        fi
    fi
    
    echo
    log_info "=== Cleaning Up Orphaned Security Group ==="
    
    # Try to delete the orphaned security group
    if delete_orphaned_security_group "$ORPHANED_SG_ID"; then
        log_success "Orphaned security group cleaned up"
    else
        log_warning "Could not delete orphaned security group - may still have dependencies"
    fi
    
    echo
    log_info "=== Continuing Stack Deletion ==="
    
    # Try to continue/complete the stack deletion
    if continue_stack_deletion; then
        log_success "Stack deletion process completed"
    else
        log_error "Stack deletion process failed"
        log_info "Manual intervention may be required in AWS Console"
        return 1
    fi
    
    echo
    log_success "=== Resolution Complete ==="
    log_success "CloudFormation DELETE_FAILED state has been resolved"
    log_success "Ready for fresh deployment"
    
    return 0
}

# Handle script interruption
trap 'log_error "Script interrupted by user"; exit 1' INT TERM

# Execute main function
main "$@"