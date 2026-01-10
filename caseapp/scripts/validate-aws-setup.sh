#!/bin/bash

# AWS Setup Validation Script
set -e

echo "🔍 Validating AWS setup for Court Case Management System deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "ℹ️  $1"
}

# Check AWS CLI installation
check_aws_cli() {
    print_info "Checking AWS CLI installation..."
    if command -v aws &> /dev/null; then
        AWS_VERSION=$(aws --version)
        print_success "AWS CLI installed: $AWS_VERSION"
    else
        print_error "AWS CLI not installed. Please install it first."
        exit 1
    fi
}

# Check AWS credentials
check_credentials() {
    print_info "Checking AWS credentials..."
    if aws sts get-caller-identity &> /dev/null; then
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        USER_ARN=$(aws sts get-caller-identity --query Arn --output text)
        print_success "AWS credentials configured"
        print_info "Account ID: $ACCOUNT_ID"
        print_info "User/Role: $USER_ARN"
    else
        print_error "AWS credentials not configured or invalid"
        print_info "Please run 'aws configure' or update your credentials"
        exit 1
    fi
}

# Check required permissions
check_permissions() {
    print_info "Checking required AWS permissions..."
    
    # Test CloudFormation permissions
    if aws cloudformation list-stacks --region us-east-1 &> /dev/null; then
        print_success "CloudFormation permissions OK"
    else
        print_error "CloudFormation permissions missing"
    fi
    
    # Test S3 permissions
    if aws s3 ls &> /dev/null; then
        print_success "S3 permissions OK"
    else
        print_error "S3 permissions missing"
    fi
    
    # Test IAM permissions
    if aws iam list-roles --max-items 1 &> /dev/null; then
        print_success "IAM permissions OK"
    else
        print_error "IAM permissions missing"
    fi
    
    # Test EC2 permissions
    if aws ec2 describe-vpcs --region us-east-1 --max-items 1 &> /dev/null; then
        print_success "EC2 permissions OK"
    else
        print_error "EC2 permissions missing"
    fi
    
    # Test ECS permissions
    if aws ecs list-clusters --region us-east-1 &> /dev/null; then
        print_success "ECS permissions OK"
    else
        print_error "ECS permissions missing"
    fi
}

# Check CDK bootstrap status
check_cdk_bootstrap() {
    print_info "Checking CDK bootstrap status..."
    
    if aws cloudformation describe-stacks --stack-name CDKToolkit --region us-east-1 &> /dev/null; then
        print_success "CDK already bootstrapped in us-east-1"
    else
        print_warning "CDK not bootstrapped in us-east-1"
        print_info "This will be done automatically during deployment"
    fi
}

# Check service limits
check_service_limits() {
    print_info "Checking AWS service limits..."
    
    # Check VPC limit
    VPC_COUNT=$(aws ec2 describe-vpcs --region us-east-1 --query 'length(Vpcs)' --output text)
    print_info "Current VPCs in us-east-1: $VPC_COUNT/5 (default limit)"
    
    if [ "$VPC_COUNT" -ge 5 ]; then
        print_warning "VPC limit may be reached. Consider cleaning up unused VPCs."
    fi
    
    # Check Elastic IPs
    EIP_COUNT=$(aws ec2 describe-addresses --region us-east-1 --query 'length(Addresses)' --output text)
    print_info "Current Elastic IPs in us-east-1: $EIP_COUNT/5 (default limit)"
    
    if [ "$EIP_COUNT" -ge 5 ]; then
        print_warning "Elastic IP limit may be reached. Consider releasing unused IPs."
    fi
}

# Check existing resources
check_existing_resources() {
    print_info "Checking for existing Court Case Management resources..."
    
    # Check if stack already exists
    if aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --region us-east-1 &> /dev/null; then
        STACK_STATUS=$(aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --region us-east-1 --query 'Stacks[0].StackStatus' --output text)
        print_info "Existing stack found with status: $STACK_STATUS"
        
        if [ "$STACK_STATUS" = "CREATE_COMPLETE" ] || [ "$STACK_STATUS" = "UPDATE_COMPLETE" ]; then
            print_success "Stack is in good state"
        else
            print_warning "Stack may need attention: $STACK_STATUS"
        fi
    else
        print_info "No existing stack found (this is normal for first deployment)"
    fi
}

# Main validation
main() {
    echo "Starting AWS setup validation..."
    echo "================================"
    
    check_aws_cli
    echo ""
    
    check_credentials
    echo ""
    
    check_permissions
    echo ""
    
    check_cdk_bootstrap
    echo ""
    
    check_service_limits
    echo ""
    
    check_existing_resources
    echo ""
    
    echo "================================"
    print_success "AWS setup validation completed!"
    echo ""
    print_info "If any errors were found above, please:"
    print_info "1. Review the AWS-CREDENTIALS-SETUP.md guide"
    print_info "2. Update your IAM permissions"
    print_info "3. Generate new access keys if needed"
    print_info "4. Update GitHub Secrets with new credentials"
    echo ""
    print_info "Ready to deploy? Push to main branch or re-run the GitHub Actions workflow."
}

# Run validation
main