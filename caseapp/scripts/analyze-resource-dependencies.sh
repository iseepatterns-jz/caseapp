#!/bin/bash

# Resource Dependency Analysis Script
# Analyzes and resolves complex AWS resource dependencies

set -euo pipefail

# Configuration
STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

log_analysis() {
    echo -e "${CYAN}[ANALYSIS]${NC} $1"
}

# Get failed CloudFormation resources
get_failed_resources() {
    log_info "Analyzing failed CloudFormation resources..."
    
    local failed_resources
    failed_resources=$(aws cloudformation describe-stack-resources \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'StackResources[?ResourceStatus==`DELETE_FAILED`]' \
        --output json 2>/dev/null || echo "[]")
    
    # Validate JSON output
    if echo "$failed_resources" | jq empty 2>/dev/null; then
        echo "$failed_resources"
    else
        echo "[]"
    fi
}

# Analyze RDS dependencies
analyze_rds_dependencies() {
    log_analysis "Analyzing RDS resource dependencies..."
    
    # Get RDS instances
    local rds_instances
    rds_instances=$(aws rds describe-db-instances \
        --region "$REGION" \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `courtcase`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [ "$rds_instances" != "[]" ]; then
        echo "$rds_instances" | jq -r '.[] | 
        "=== RDS Instance Analysis ===
        Instance ID: \(.DBInstanceIdentifier)
        Status: \(.DBInstanceStatus)
        Deletion Protection: \(.DeletionProtection)
        Subnet Group: \(.DBSubnetGroup.DBSubnetGroupName)
        Security Groups: \([.VpcSecurityGroups[].VpcSecurityGroupId] | join(", "))
        Engine: \(.Engine) \(.EngineVersion)
        Instance Class: \(.DBInstanceClass)
        Allocated Storage: \(.AllocatedStorage)GB
        Multi-AZ: \(.MultiAZ)
        Backup Retention: \(.BackupRetentionPeriod) days
        Created: \(.InstanceCreateTime)
        "' 2>/dev/null || log_warning "Failed to parse RDS instance details"
        
        # Analyze each RDS instance's dependencies
        echo "$rds_instances" | jq -r '.[].DBInstanceIdentifier' | while read -r db_instance; do
            analyze_single_rds_instance "$db_instance"
        done
    else
        log_info "No RDS instances found"
    fi
}

# Analyze single RDS instance dependencies
analyze_single_rds_instance() {
    local db_instance="$1"
    
    log_analysis "Analyzing dependencies for RDS instance: $db_instance"
    
    # Get detailed RDS instance information
    local rds_details
    rds_details=$(aws rds describe-db-instances \
        --db-instance-identifier "$db_instance" \
        --region "$REGION" \
        --output json 2>/dev/null || echo "{}")
    
    # Extract subnet group and security groups
    local subnet_group
    local security_groups
    subnet_group=$(echo "$rds_details" | jq -r '.DBInstances[0].DBSubnetGroup.DBSubnetGroupName // "none"')
    security_groups=$(echo "$rds_details" | jq -r '.DBInstances[0].VpcSecurityGroups[].VpcSecurityGroupId' | tr '\n' ' ')
    
    echo "  Subnet Group: $subnet_group"
    echo "  Security Groups: $security_groups"
    
    # Analyze subnet group dependencies
    if [ "$subnet_group" != "none" ]; then
        analyze_subnet_group_dependencies "$subnet_group"
    fi
    
    # Analyze security group dependencies
    for sg_id in $security_groups; do
        if [ -n "$sg_id" ]; then
            analyze_security_group_dependencies "$sg_id"
        fi
    done
    
    # Check for automated backups
    local automated_backups
    automated_backups=$(aws rds describe-db-instance-automated-backups \
        --db-instance-identifier "$db_instance" \
        --region "$REGION" \
        --query 'DBInstanceAutomatedBackups[].{BackupArn:DBInstanceAutomatedBackupArn,Status:Status}' \
        --output table 2>/dev/null || echo "No automated backups found")
    
    echo "  Automated Backups:"
    echo "$automated_backups" | sed 's/^/    /'
    
    # Check for read replicas
    local read_replicas
    read_replicas=$(echo "$rds_details" | jq -r '.DBInstances[0].ReadReplicaDBInstanceIdentifiers[]?' 2>/dev/null || echo "")
    
    if [ -n "$read_replicas" ]; then
        echo "  Read Replicas: $read_replicas"
    else
        echo "  Read Replicas: None"
    fi
    
    echo
}

# Analyze subnet group dependencies
analyze_subnet_group_dependencies() {
    local subnet_group="$1"
    
    log_analysis "Analyzing subnet group dependencies: $subnet_group"
    
    # Get subnet group details
    local subnet_details
    subnet_details=$(aws rds describe-db-subnet-groups \
        --db-subnet-group-name "$subnet_group" \
        --region "$REGION" \
        --output json 2>/dev/null || echo "{}")
    
    # Extract subnets
    local subnets
    subnets=$(echo "$subnet_details" | jq -r '.DBSubnetGroups[0].Subnets[].SubnetIdentifier' 2>/dev/null | tr '\n' ' ')
    
    echo "    Subnets in group: $subnets"
    
    # Check which DB instances are using this subnet group
    local using_instances
    using_instances=$(aws rds describe-db-instances \
        --region "$REGION" \
        --query "DBInstances[?DBSubnetGroup.DBSubnetGroupName=='$subnet_group'].DBInstanceIdentifier" \
        --output text 2>/dev/null || echo "")
    
    echo "    Used by DB instances: $using_instances"
    
    # Analyze each subnet
    for subnet_id in $subnets; do
        if [ -n "$subnet_id" ]; then
            analyze_subnet_dependencies "$subnet_id"
        fi
    done
}

# Analyze subnet dependencies
analyze_subnet_dependencies() {
    local subnet_id="$1"
    
    # Get network interfaces in this subnet
    local enis
    enis=$(aws ec2 describe-network-interfaces \
        --filters "Name=subnet-id,Values=$subnet_id" \
        --region "$REGION" \
        --query 'NetworkInterfaces[].{NetworkInterfaceId:NetworkInterfaceId,Status:Status,Description:Description}' \
        --output table 2>/dev/null || echo "No network interfaces found")
    
    echo "      Subnet $subnet_id network interfaces:"
    echo "$enis" | sed 's/^/        /'
}

# Analyze security group dependencies
analyze_security_group_dependencies() {
    local sg_id="$1"
    
    log_analysis "Analyzing security group dependencies: $sg_id"
    
    # Get security group details
    local sg_details
    sg_details=$(aws ec2 describe-security-groups \
        --group-ids "$sg_id" \
        --region "$REGION" \
        --output json 2>/dev/null || echo "{}")
    
    local sg_name
    sg_name=$(echo "$sg_details" | jq -r '.SecurityGroups[0].GroupName // "unknown"')
    
    echo "    Security Group Name: $sg_name"
    
    # Find network interfaces using this security group
    local enis
    enis=$(aws ec2 describe-network-interfaces \
        --filters "Name=group-id,Values=$sg_id" \
        --region "$REGION" \
        --query 'NetworkInterfaces[]' \
        --output json 2>/dev/null || echo "[]")
    
    if [ "$enis" != "[]" ]; then
        echo "    Network Interfaces using this security group:"
        echo "$enis" | jq -r '.[] | 
        "      ENI: \(.NetworkInterfaceId)
        Status: \(.Status)
        Description: \(.Description // "N/A")
        Owner: \(.Attachment.InstanceOwnerId // "N/A")
        Instance: \(.Attachment.InstanceId // "N/A")"' 2>/dev/null || echo "      Failed to parse ENI details"
    else
        echo "    No network interfaces using this security group"
    fi
    
    # Check for EC2 instances using this security group
    local instances
    instances=$(aws ec2 describe-instances \
        --filters "Name=instance.group-id,Values=$sg_id" \
        --region "$REGION" \
        --query 'Reservations[].Instances[].{InstanceId:InstanceId,State:State.Name}' \
        --output table 2>/dev/null || echo "No EC2 instances found")
    
    echo "    EC2 instances using this security group:"
    echo "$instances" | sed 's/^/      /'
    
    # Check for RDS instances using this security group
    local rds_instances
    rds_instances=$(aws rds describe-db-instances \
        --region "$REGION" \
        --query "DBInstances[?VpcSecurityGroups[?VpcSecurityGroupId=='$sg_id']].DBInstanceIdentifier" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$rds_instances" ]; then
        echo "    RDS instances using this security group: $rds_instances"
    else
        echo "    No RDS instances using this security group"
    fi
    
    # Check for load balancers using this security group
    local load_balancers
    load_balancers=$(aws elbv2 describe-load-balancers \
        --region "$REGION" \
        --query "LoadBalancers[?SecurityGroups[?contains(@, '$sg_id')]].LoadBalancerName" \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$load_balancers" ]; then
        echo "    Load balancers using this security group: $load_balancers"
    else
        echo "    No load balancers using this security group"
    fi
    
    echo
}

# Generate dependency resolution plan
generate_resolution_plan() {
    log_info "Generating dependency resolution plan..."
    
    echo
    echo "=================================="
    echo "DEPENDENCY RESOLUTION PLAN"
    echo "=================================="
    echo
    
    # Get failed resources
    local failed_resources
    failed_resources=$(get_failed_resources)
    
    if [ "$failed_resources" != "[]" ] && [ -n "$failed_resources" ]; then
        echo "FAILED RESOURCES:"
        if echo "$failed_resources" | jq empty 2>/dev/null; then
            echo "$failed_resources" | jq -r '.[] | 
            "- \(.LogicalResourceId) (\(.ResourceType))
              Physical ID: \(.PhysicalResourceId // "N/A")
              Status: \(.ResourceStatus)
              Reason: \(.ResourceStatusReason // "N/A")"' 2>/dev/null || echo "Failed to parse resource details"
        else
            echo "Invalid JSON response from CloudFormation API"
        fi
        echo
    fi
    
    echo "RESOLUTION STEPS:"
    echo "=================="
    echo
    
    # Step 1: RDS Instance Resolution
    echo "1. RDS INSTANCE RESOLUTION"
    echo "   Problem: RDS instances are preventing subnet group and security group deletion"
    echo "   Solution Options:"
    echo "   a) Delete RDS instances (DESTRUCTIVE - will lose data)"
    echo "      - Disable deletion protection if enabled"
    echo "      - Delete automated backups"
    echo "      - Delete the RDS instance"
    echo "   b) Modify RDS instances to use different resources"
    echo "      - Move to different subnet group"
    echo "      - Change security groups"
    echo "   c) Retain RDS resources and clean up stack"
    echo "      - Use CloudFormation resource retention"
    echo "      - Manually manage RDS resources outside of stack"
    echo
    
    # Step 2: Security Group Resolution
    echo "2. SECURITY GROUP RESOLUTION"
    echo "   Problem: Security groups have dependent network interfaces"
    echo "   Solution:"
    echo "   - Network interfaces will be automatically cleaned up when RDS instances are deleted"
    echo "   - If retaining RDS instances, security groups must also be retained"
    echo "   - Manual cleanup required if resources are retained"
    echo
    
    # Step 3: Subnet Group Resolution
    echo "3. SUBNET GROUP RESOLUTION"
    echo "   Problem: DB subnet group is in use by RDS instances"
    echo "   Solution:"
    echo "   - Subnet group will be automatically deletable after RDS instances are removed"
    echo "   - If retaining RDS instances, subnet group must also be retained"
    echo
    
    # Step 4: CloudFormation Stack Resolution
    echo "4. CLOUDFORMATION STACK RESOLUTION"
    echo "   Options:"
    echo "   a) Complete cleanup (RECOMMENDED for fresh deployment)"
    echo "      - Delete all RDS instances and dependencies"
    echo "      - Allow CloudFormation to complete stack deletion"
    echo "   b) Partial cleanup with resource retention"
    echo "      - Retain problematic resources"
    echo "      - Delete stack while keeping retained resources"
    echo "      - Manually manage retained resources"
    echo "   c) Continue rollback with resource skipping"
    echo "      - Skip failed resources during rollback"
    echo "      - May leave orphaned resources"
    echo
    
    echo "RECOMMENDED APPROACH:"
    echo "===================="
    echo "For a fresh deployment, complete cleanup is recommended:"
    echo "1. Disable RDS deletion protection"
    echo "2. Delete RDS instances (with confirmation)"
    echo "3. Wait for RDS deletion to complete"
    echo "4. Delete CloudFormation stack"
    echo "5. Verify all resources are cleaned up"
    echo "6. Proceed with fresh deployment"
    echo
    
    echo "MANUAL CLEANUP COMMANDS:"
    echo "========================"
    
    # Generate specific cleanup commands
    local rds_instances
    rds_instances=$(aws rds describe-db-instances \
        --region "$REGION" \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `courtcase`)].DBInstanceIdentifier' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$rds_instances" ]; then
        echo "# Disable deletion protection and delete RDS instances:"
        for db_instance in $rds_instances; do
            echo "aws rds modify-db-instance --db-instance-identifier $db_instance --no-deletion-protection --region $REGION"
            echo "aws rds delete-db-instance --db-instance-identifier $db_instance --skip-final-snapshot --delete-automated-backups --region $REGION"
            echo "aws rds wait db-instance-deleted --db-instance-identifier $db_instance --region $REGION"
        done
        echo
    fi
    
    echo "# Delete CloudFormation stack after RDS cleanup:"
    echo "aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION"
    echo "aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION"
    echo
    
    echo "# Alternative: Force delete with resource retention:"
    local retain_resources
    retain_resources=$(aws cloudformation describe-stack-resources \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'StackResources[?ResourceStatus==`DELETE_FAILED`].LogicalResourceId' \
        --output text 2>/dev/null | tr '\t' ',' || echo "")
    
    if [ -n "$retain_resources" ]; then
        echo "aws cloudformation delete-stack --stack-name $STACK_NAME --retain-resources $retain_resources --region $REGION"
    fi
}

# Main execution
main() {
    log_info "Starting comprehensive resource dependency analysis..."
    log_info "Stack: $STACK_NAME"
    log_info "Region: $REGION"
    echo
    
    # Analyze RDS dependencies
    analyze_rds_dependencies
    echo
    
    # Generate resolution plan
    generate_resolution_plan
    
    log_success "Dependency analysis completed!"
}

# Execute main function
main "$@"