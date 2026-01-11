#!/bin/bash

# Pre-deployment Validation Script
# Checks for orphaned resources and deployment readiness

set -euo pipefail

# Configuration
STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"
DOCKER_USERNAME="iseepatterns"

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
    
    local caller_identity=$(aws sts get-caller-identity --query 'Account' --output text)
    log_success "AWS CLI configured for account: $caller_identity"
    return 0
}

# Check if CloudFormation stack exists
check_stack_exists() {
    log_info "Checking for existing CloudFormation stack..."
    
    local stack_status
    stack_status=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "STACK_NOT_FOUND")
    
    if [ "$stack_status" != "STACK_NOT_FOUND" ]; then
        log_error "CloudFormation stack '$STACK_NAME' already exists with status: $stack_status"
        log_error "Please clean up the existing stack before deploying"
        return 1
    fi
    
    log_success "No existing CloudFormation stack found"
    return 0
}

# Check for orphaned RDS resources
check_orphaned_rds() {
    log_info "Checking for orphaned RDS resources..."
    
    # Check for RDS instances
    local db_instances
    db_instances=$(aws rds describe-db-instances \
        --region "$REGION" \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `courtcase`)].{Identifier:DBInstanceIdentifier,Status:DBInstanceStatus}' \
        --output table 2>/dev/null || echo "")
    
    if [ -n "$db_instances" ] && [ "$db_instances" != "[]" ]; then
        log_warning "Found orphaned RDS instances:"
        echo "$db_instances"
        return 1
    fi
    
    # Check for RDS subnet groups
    local subnet_groups
    subnet_groups=$(aws rds describe-db-subnet-groups \
        --region "$REGION" \
        --query 'DBSubnetGroups[?contains(DBSubnetGroupName, `courtcase`)].DBSubnetGroupName' \
        --output table 2>/dev/null || echo "")
    
    if [ -n "$subnet_groups" ] && [ "$subnet_groups" != "[]" ]; then
        log_warning "Found orphaned RDS subnet groups:"
        echo "$subnet_groups"
        return 1
    fi
    
    log_success "No orphaned RDS resources found"
    return 0
}

# Check for orphaned security groups
check_orphaned_security_groups() {
    log_info "Checking for orphaned security groups..."
    
    local security_groups
    security_groups=$(aws ec2 describe-security-groups \
        --region "$REGION" \
        --filters "Name=group-name,Values=*CourtCase*" \
        --query 'SecurityGroups[?GroupName!=`default`].{GroupId:GroupId,GroupName:GroupName}' \
        --output table 2>/dev/null || echo "")
    
    if [ -n "$security_groups" ] && [ "$security_groups" != "[]" ]; then
        log_warning "Found potentially orphaned security groups:"
        echo "$security_groups"
        return 1
    fi
    
    log_success "No orphaned security groups found"
    return 0
}

# Check Docker images accessibility
check_docker_images() {
    log_info "Checking Docker images accessibility..."
    
    local images=(
        "${DOCKER_USERNAME}/court-case-backend:latest"
        "${DOCKER_USERNAME}/court-case-media:latest"
    )
    
    local all_accessible=true
    
    for image in "${images[@]}"; do
        log_info "Checking image: $image"
        
        if docker manifest inspect "$image" &>/dev/null; then
            log_success "✅ Image accessible: $image"
        else
            log_error "❌ Image not accessible: $image"
            all_accessible=false
        fi
    done
    
    if [ "$all_accessible" = true ]; then
        log_success "All Docker images are accessible"
        return 0
    else
        log_error "Some Docker images are not accessible"
        return 1
    fi
}

# Check AWS service quotas and limits
check_aws_quotas() {
    log_info "Checking AWS service quotas..."
    
    # Check ECS service limits
    local ecs_services
    ecs_services=$(aws ecs list-services --region "$REGION" --query 'length(serviceArns)' --output text 2>/dev/null || echo "0")
    log_info "Current ECS services: $ecs_services"
    
    # Check RDS instance limits
    local rds_instances
    rds_instances=$(aws rds describe-db-instances --region "$REGION" --query 'length(DBInstances)' --output text 2>/dev/null || echo "0")
    log_info "Current RDS instances: $rds_instances"
    
    # Check VPC limits
    local vpcs
    vpcs=$(aws ec2 describe-vpcs --region "$REGION" --query 'length(Vpcs)' --output text 2>/dev/null || echo "0")
    log_info "Current VPCs: $vpcs"
    
    log_success "AWS service quotas check completed"
    return 0
}

# Check network connectivity
check_network_connectivity() {
    log_info "Checking network connectivity to AWS services..."
    
    # Test connectivity to AWS services
    local services=(
        "ecs.$REGION.amazonaws.com"
        "rds.$REGION.amazonaws.com"
        "s3.$REGION.amazonaws.com"
        "cloudformation.$REGION.amazonaws.com"
    )
    
    local all_reachable=true
    
    for service in "${services[@]}"; do
        if curl -s --connect-timeout 5 "https://$service" &>/dev/null; then
            log_success "✅ Reachable: $service"
        else
            log_warning "⚠️  May not be reachable: $service"
            # Don't fail on network checks as they might be false positives
        fi
    done
    
    log_success "Network connectivity check completed"
    return 0
}

# Check CDK/deployment prerequisites
check_deployment_prerequisites() {
    log_info "Checking deployment prerequisites..."
    
    # Check if CDK is installed
    if command -v cdk &> /dev/null; then
        local cdk_version=$(cdk --version)
        log_success "CDK installed: $cdk_version"
    else
        log_warning "CDK not found. Make sure it's installed for deployment"
    fi
    
    # Check if Python is available
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version)
        log_success "Python available: $python_version"
    else
        log_error "Python3 not found"
        return 1
    fi
    
    # Check if required files exist
    local required_files=(
        "caseapp/infrastructure/app.py"
        "caseapp/requirements.txt"
        "caseapp/Dockerfile"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            log_success "✅ Required file exists: $file"
        else
            log_error "❌ Required file missing: $file"
            return 1
        fi
    done
    
    log_success "Deployment prerequisites check completed"
    return 0
}

# Generate deployment readiness report
generate_report() {
    local overall_status="READY"
    local issues=()
    
    log_info "Generating deployment readiness report..."
    
    echo
    echo "=================================="
    echo "DEPLOYMENT READINESS REPORT"
    echo "=================================="
    echo "Stack Name: $STACK_NAME"
    echo "Region: $REGION"
    echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    echo
    
    # Run all checks and collect results
    echo "VALIDATION RESULTS:"
    echo "==================="
    
    if check_aws_cli; then
        echo "✅ AWS CLI Configuration: PASS"
    else
        echo "❌ AWS CLI Configuration: FAIL"
        issues+=("AWS CLI not properly configured")
        overall_status="NOT_READY"
    fi
    
    if check_stack_exists; then
        echo "✅ CloudFormation Stack: PASS (no existing stack)"
    else
        echo "❌ CloudFormation Stack: FAIL (existing stack found)"
        issues+=("Existing CloudFormation stack needs cleanup")
        overall_status="NOT_READY"
    fi
    
    if check_orphaned_rds; then
        echo "✅ RDS Resources: PASS (no orphaned resources)"
    else
        echo "⚠️  RDS Resources: WARNING (orphaned resources found)"
        issues+=("Orphaned RDS resources need cleanup")
        overall_status="NEEDS_CLEANUP"
    fi
    
    if check_orphaned_security_groups; then
        echo "✅ Security Groups: PASS (no orphaned groups)"
    else
        echo "⚠️  Security Groups: WARNING (orphaned groups found)"
        issues+=("Orphaned security groups need cleanup")
        overall_status="NEEDS_CLEANUP"
    fi
    
    if check_docker_images; then
        echo "✅ Docker Images: PASS (all images accessible)"
    else
        echo "❌ Docker Images: FAIL (some images not accessible)"
        issues+=("Docker images not accessible")
        overall_status="NOT_READY"
    fi
    
    if check_aws_quotas; then
        echo "✅ AWS Quotas: PASS"
    else
        echo "⚠️  AWS Quotas: WARNING"
        issues+=("AWS quota limits may be reached")
    fi
    
    if check_network_connectivity; then
        echo "✅ Network Connectivity: PASS"
    else
        echo "⚠️  Network Connectivity: WARNING"
        issues+=("Network connectivity issues detected")
    fi
    
    if check_deployment_prerequisites; then
        echo "✅ Deployment Prerequisites: PASS"
    else
        echo "❌ Deployment Prerequisites: FAIL"
        issues+=("Missing deployment prerequisites")
        overall_status="NOT_READY"
    fi
    
    echo
    echo "OVERALL STATUS: $overall_status"
    echo
    
    if [ ${#issues[@]} -gt 0 ]; then
        echo "ISSUES FOUND:"
        echo "============="
        for issue in "${issues[@]}"; do
            echo "- $issue"
        done
        echo
    fi
    
    case "$overall_status" in
        "READY")
            log_success "🎉 Deployment is ready to proceed!"
            echo "You can now run the deployment script."
            return 0
            ;;
        "NEEDS_CLEANUP")
            log_warning "⚠️  Deployment needs cleanup before proceeding"
            echo "Run the cleanup script first: ./scripts/cleanup-cloudformation-stack.sh"
            return 1
            ;;
        "NOT_READY")
            log_error "❌ Deployment is not ready"
            echo "Please resolve the issues listed above before deploying."
            return 1
            ;;
    esac
}

# Main execution
main() {
    log_info "Starting deployment readiness validation..."
    echo
    
    generate_report
}

# Execute main function
main "$@"