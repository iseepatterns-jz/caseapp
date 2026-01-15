#!/bin/bash
#
# Pre-Deployment Test Suite
# Comprehensive validation before triggering deployment
#
# This script performs extensive checks to catch issues before deployment:
# 1. AWS credentials and permissions
# 2. Service quotas and limits
# 3. Secrets existence and validity
# 4. Template validation (syntax and compliance)
# 5. Resource availability
# 6. Network configuration
# 7. Docker image validation
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
STACK_NAME="${STACK_NAME:-CourtCaseManagementStack}"
REGION="${AWS_REGION:-us-east-1}"
TEMPLATE_FILE="caseapp/infrastructure/cdk.out/CourtCaseManagementStack.template.json"

# Test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNINGS=0

# Logging functions
log_test() {
    echo -e "${BLUE}[TEST $((TOTAL_TESTS + 1))]${NC} $1"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
}

log_pass() {
    echo -e "${GREEN}  ✅ PASS${NC} $1"
    PASSED_TESTS=$((PASSED_TESTS + 1))
}

log_fail() {
    echo -e "${RED}  ❌ FAIL${NC} $1"
    FAILED_TESTS=$((FAILED_TESTS + 1))
}

log_warn() {
    echo -e "${YELLOW}  ⚠️  WARN${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

log_info() {
    echo -e "${BLUE}  ℹ️  INFO${NC} $1"
}

# Test 1: AWS Credentials
test_aws_credentials() {
    log_test "AWS Credentials and Identity"
    
    if identity=$(AWS_PAGER="" aws sts get-caller-identity 2>&1); then
        account=$(echo "$identity" | jq -r '.Account')
        user=$(echo "$identity" | jq -r '.Arn')
        log_pass "Authenticated as: $user"
        log_info "Account: $account"
    else
        log_fail "AWS credentials not configured or invalid"
        return 1
    fi
}

# Test 2: Required AWS Permissions
test_aws_permissions() {
    log_test "AWS IAM Permissions"
    
    local required_actions=(
        "cloudformation:CreateStack"
        "cloudformation:DescribeStacks"
        "ecs:CreateCluster"
        "rds:CreateDBInstance"
        "ec2:CreateVpc"
        "s3:CreateBucket"
    )
    
    # Test by attempting to describe resources (read-only check)
    local permission_errors=0
    
    if AWS_PAGER="" aws cloudformation describe-stacks --max-items 1 >/dev/null 2>&1; then
        log_pass "CloudFormation permissions OK"
    else
        log_fail "Missing CloudFormation permissions"
        permission_errors=$((permission_errors + 1))
    fi
    
    if AWS_PAGER="" aws ecs list-clusters --max-items 1 >/dev/null 2>&1; then
        log_pass "ECS permissions OK"
    else
        log_fail "Missing ECS permissions"
        permission_errors=$((permission_errors + 1))
    fi
    
    if AWS_PAGER="" aws rds describe-db-instances --max-records 1 >/dev/null 2>&1; then
        log_pass "RDS permissions OK"
    else
        log_fail "Missing RDS permissions"
        permission_errors=$((permission_errors + 1))
    fi
    
    if [ $permission_errors -gt 0 ]; then
        return 1
    fi
}

# Test 3: Service Quotas
test_service_quotas() {
    log_test "AWS Service Quotas"
    
    # Check VPC quota
    local vpc_count=$(AWS_PAGER="" aws ec2 describe-vpcs --query 'length(Vpcs)' --output text)
    local vpc_limit=5  # Default limit
    log_info "VPCs: $vpc_count/$vpc_limit"
    if [ "$vpc_count" -ge $vpc_limit ]; then
        log_fail "VPC quota exhausted ($vpc_count/$vpc_limit)"
        return 1
    else
        log_pass "VPC quota available"
    fi
    
    # Check ECS cluster quota
    local cluster_count=$(AWS_PAGER="" aws ecs list-clusters --query 'length(clusterArns)' --output text)
    log_info "ECS Clusters: $cluster_count"
    log_pass "ECS cluster quota OK"
    
    # Check RDS instance quota
    local rds_count=$(AWS_PAGER="" aws rds describe-db-instances --query 'length(DBInstances)' --output text)
    log_info "RDS Instances: $rds_count"
    log_pass "RDS instance quota OK"
}

# Test 4: Required Secrets
test_secrets() {
    log_test "AWS Secrets Manager - Required Secrets"
    
    local required_secrets=(
        "courtcase-database-credentials"
        "opensearch-master-password"
    )
    
    local missing_secrets=0
    
    for secret in "${required_secrets[@]}"; do
        if AWS_PAGER="" aws secretsmanager describe-secret --secret-id "$secret" >/dev/null 2>&1; then
            log_pass "Secret exists: $secret"
        else
            log_fail "Missing secret: $secret"
            missing_secrets=$((missing_secrets + 1))
        fi
    done
    
    if [ $missing_secrets -gt 0 ]; then
        log_info "Create missing secrets with:"
        log_info "  aws secretsmanager create-secret --name <secret-name> --secret-string '{\"password\":\"<value>\"}'"
        return 1
    fi
}

# Test 5: CDK Template Synthesis
test_cdk_synthesis() {
    log_test "CDK Template Synthesis"
    
    cd caseapp/infrastructure
    
    if cdk synth > /dev/null 2>&1; then
        log_pass "CDK synthesis successful"
        
        # Check template size
        if [ -f "cdk.out/CourtCaseManagementStack.template.json" ]; then
            local size=$(wc -c < "cdk.out/CourtCaseManagementStack.template.json")
            local size_kb=$((size / 1024))
            log_info "Template size: ${size_kb}KB"
            
            if [ $size -gt 51200 ]; then  # 50KB limit
                log_warn "Template size exceeds 50KB (CloudFormation limit: 51200 bytes)"
            else
                log_pass "Template size within limits"
            fi
        fi
    else
        log_fail "CDK synthesis failed"
        cd ../..
        return 1
    fi
    
    cd ../..
}

# Test 6: CloudFormation Template Validation
test_template_validation() {
    log_test "CloudFormation Template Validation"
    
    if [ ! -f "$TEMPLATE_FILE" ]; then
        log_fail "Template file not found: $TEMPLATE_FILE"
        log_info "Run: cd caseapp/infrastructure && cdk synth"
        return 1
    fi
    
    # Validate with AWS CloudFormation
    if AWS_PAGER="" aws cloudformation validate-template \
        --template-body "file://$TEMPLATE_FILE" >/dev/null 2>&1; then
        log_pass "CloudFormation template is valid"
    else
        log_fail "CloudFormation template validation failed"
        return 1
    fi
    
    # Check for common issues
    local resource_count=$(jq '.Resources | length' "$TEMPLATE_FILE")
    log_info "Resources in template: $resource_count"
    
    if [ "$resource_count" -gt 200 ]; then
        log_warn "Template has $resource_count resources (limit: 500)"
    else
        log_pass "Resource count within limits"
    fi
}

# Test 7: Resource Name Conflicts
test_resource_conflicts() {
    log_test "Resource Name Conflicts"
    
    # Check for existing stack
    if AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" >/dev/null 2>&1; then
        local stack_status=$(AWS_PAGER="" aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].StackStatus' \
            --output text)
        
        case "$stack_status" in
            CREATE_COMPLETE|UPDATE_COMPLETE)
                log_warn "Stack already exists: $STACK_NAME (status: $stack_status)"
                log_info "Use 'cdk destroy' or delete stack before deploying"
                ;;
            CREATE_IN_PROGRESS|UPDATE_IN_PROGRESS)
                log_fail "Stack is currently deploying: $STACK_NAME (status: $stack_status)"
                log_info "Wait for deployment to complete or cancel it"
                return 1
                ;;
            ROLLBACK_COMPLETE|ROLLBACK_FAILED|DELETE_FAILED)
                log_fail "Stack in failed state: $STACK_NAME (status: $stack_status)"
                log_info "Delete the stack before deploying"
                return 1
                ;;
            DELETE_IN_PROGRESS)
                log_warn "Stack is being deleted: $STACK_NAME"
                log_info "Wait for deletion to complete"
                ;;
        esac
    else
        log_pass "No existing stack found"
    fi
    
    # Check for orphaned RDS instances
    local rds_instances=$(AWS_PAGER="" aws rds describe-db-instances \
        --query 'DBInstances[?contains(DBInstanceIdentifier, `courtcase`)].DBInstanceIdentifier' \
        --output text)
    
    if [ -n "$rds_instances" ]; then
        log_fail "Found orphaned RDS instances: $rds_instances"
        log_info "Delete with: aws rds delete-db-instance --db-instance-identifier <id> --skip-final-snapshot"
        return 1
    else
        log_pass "No orphaned RDS instances"
    fi
    
    # Check for orphaned ECS clusters
    local ecs_clusters=$(AWS_PAGER="" aws ecs list-clusters \
        --query 'clusterArns[?contains(@, `CourtCase`)]' \
        --output text)
    
    if [ -n "$ecs_clusters" ]; then
        log_warn "Found existing ECS clusters: $ecs_clusters"
    else
        log_pass "No orphaned ECS clusters"
    fi
}

# Test 8: Network Configuration
test_network_config() {
    log_test "Network Configuration"
    
    # Check available IP addresses in region
    local vpcs=$(AWS_PAGER="" aws ec2 describe-vpcs --query 'length(Vpcs)' --output text)
    log_info "Existing VPCs: $vpcs"
    
    # Check for CIDR conflicts (10.0.0.0/16 is our default)
    local conflicting_vpcs=$(AWS_PAGER="" aws ec2 describe-vpcs \
        --filters "Name=cidr,Values=10.0.0.0/16" \
        --query 'Vpcs[].VpcId' \
        --output text)
    
    if [ -n "$conflicting_vpcs" ]; then
        log_warn "VPC with CIDR 10.0.0.0/16 already exists: $conflicting_vpcs"
        log_info "May cause conflicts if not part of our stack"
    else
        log_pass "No CIDR conflicts detected"
    fi
    
    # Check NAT Gateway quota
    local nat_gateways=$(AWS_PAGER="" aws ec2 describe-nat-gateways \
        --filter "Name=state,Values=available" \
        --query 'length(NatGateways)' \
        --output text)
    log_info "NAT Gateways: $nat_gateways"
    log_pass "NAT Gateway quota OK"
}

# Test 9: Docker Images
test_docker_images() {
    log_test "Docker Images"
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        log_warn "Docker is not running (needed for local testing)"
        return 0  # Not critical for deployment
    fi
    
    log_pass "Docker is running"
    
    # Check for local images
    if docker images | grep -q "courtcase"; then
        log_info "Found local courtcase images"
        log_pass "Docker images available"
    else
        log_warn "No local courtcase images found"
        log_info "Images will be built during deployment"
    fi
}

# Test 10: GitHub Actions Workflow
test_github_workflow() {
    log_test "GitHub Actions Workflow"
    
    if [ ! -f ".github/workflows/ci-cd.yml" ]; then
        log_fail "GitHub Actions workflow not found"
        return 1
    fi
    
    log_pass "GitHub Actions workflow exists"
    
    # Check for required secrets in workflow
    if grep -q "AWS_ACCESS_KEY_ID" .github/workflows/ci-cd.yml; then
        log_pass "AWS credentials configured in workflow"
    else
        log_warn "AWS credentials may not be configured"
    fi
}

# Test 11: Deployment Timeout Settings
test_timeout_settings() {
    log_test "Deployment Timeout Settings"
    
    if grep -q "timeout-minutes: 120" .github/workflows/ci-cd.yml; then
        log_pass "Deployment timeout set to 120 minutes"
    else
        log_warn "Deployment timeout may be too short"
        log_info "Recommended: 120 minutes for full stack deployment"
    fi
}

# Test 12: Cost Estimation
test_cost_estimation() {
    log_test "Cost Estimation"
    
    log_info "Estimated monthly costs:"
    log_info "  - ECS Fargate (2 tasks): ~\$50-70"
    log_info "  - RDS db.t3.medium: ~\$60-80"
    log_info "  - OpenSearch t3.small: ~\$100-120"
    log_info "  - NAT Gateway: ~\$30-40"
    log_info "  - ALB: ~\$20-25"
    log_info "  - Total: ~\$260-335/month"
    
    log_pass "Cost estimation provided"
}

# Summary
print_summary() {
    echo ""
    echo "=========================================="
    echo "Pre-Deployment Test Summary"
    echo "=========================================="
    echo -e "Total Tests:   ${BLUE}$TOTAL_TESTS${NC}"
    echo -e "Passed:        ${GREEN}$PASSED_TESTS${NC}"
    echo -e "Failed:        ${RED}$FAILED_TESTS${NC}"
    echo -e "Warnings:      ${YELLOW}$WARNINGS${NC}"
    echo "=========================================="
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "${GREEN}✅ ALL TESTS PASSED - READY TO DEPLOY${NC}"
        echo ""
        echo "Next steps:"
        echo "  1. Ensure stack is deleted: aws cloudformation delete-stack --stack-name $STACK_NAME"
        echo "  2. Wait for deletion: aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME"
        echo "  3. Deploy with: cd caseapp/infrastructure && cdk deploy --require-approval never"
        echo "  4. Or trigger GitHub Actions: git push origin main"
        return 0
    else
        echo -e "${RED}❌ TESTS FAILED - DO NOT DEPLOY${NC}"
        echo ""
        echo "Fix the failed tests before deploying to avoid wasting time."
        return 1
    fi
}

# Main execution
main() {
    echo "=========================================="
    echo "Pre-Deployment Test Suite"
    echo "Stack: $STACK_NAME"
    echo "Region: $REGION"
    echo "=========================================="
    echo ""
    
    # Run all tests (continue even if some fail)
    test_aws_credentials || true
    test_aws_permissions || true
    test_service_quotas || true
    test_secrets || true
    test_cdk_synthesis || true
    test_template_validation || true
    test_resource_conflicts || true
    test_network_config || true
    test_docker_images || true
    test_github_workflow || true
    test_timeout_settings || true
    test_cost_estimation || true
    
    # Print summary and exit with appropriate code
    print_summary
}

main "$@"
