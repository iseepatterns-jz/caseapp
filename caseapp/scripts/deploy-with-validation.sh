#!/bin/bash

# Comprehensive Deployment Script with Validation and Retry Logic
# Implements exponential backoff and pre-deployment validation

set -euo pipefail

# Configuration
STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"
MAX_RETRIES=3
BASE_DELAY=30
MAX_DELAY=300

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

# Calculate exponential backoff delay
calculate_delay() {
    local attempt=$1
    local delay=$((BASE_DELAY * (2 ** (attempt - 1))))
    
    if [ $delay -gt $MAX_DELAY ]; then
        delay=$MAX_DELAY
    fi
    
    echo $delay
}

# Run pre-deployment validation
run_validation() {
    log_info "Running pre-deployment validation..."
    
    # Run the comprehensive deployment validation gates
    if [ -f "./scripts/deployment-validation-gates.sh" ]; then
        if ./scripts/deployment-validation-gates.sh; then
            log_success "Deployment validation gates passed"
            return 0
        else
            local exit_code=$?
            if [ $exit_code -eq 1 ]; then
                log_warning "Deployment validation gates completed with warnings"
                log_info "Proceeding with deployment despite warnings..."
                return 0
            else
                log_error "Deployment validation gates failed"
                return 1
            fi
        fi
    elif [ -f "./scripts/validate-deployment-readiness.sh" ]; then
        log_info "Using legacy validation script..."
        if ./scripts/validate-deployment-readiness.sh; then
            log_success "Pre-deployment validation passed"
            return 0
        else
            log_error "Pre-deployment validation failed"
            return 1
        fi
    else
        log_warning "No validation script found, skipping validation"
        return 0
    fi
}

# Check if cleanup is needed
check_cleanup_needed() {
    local stack_status
    stack_status=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "STACK_NOT_FOUND")
    
    case "$stack_status" in
        "ROLLBACK_FAILED"|"DELETE_FAILED"|"CREATE_FAILED"|"UPDATE_ROLLBACK_FAILED")
            return 0  # Cleanup needed
            ;;
        "STACK_NOT_FOUND")
            return 1  # No cleanup needed
            ;;
        *)
            log_warning "Stack exists with status: $stack_status"
            return 0  # May need cleanup
            ;;
    esac
}

# Run cleanup if needed
run_cleanup() {
    log_info "Checking if cleanup is needed..."
    
    if check_cleanup_needed; then
        log_warning "Cleanup is required before deployment"
        
        if [ -f "./scripts/cleanup-cloudformation-stack.sh" ]; then
            log_info "Running cleanup script..."
            
            if ./scripts/cleanup-cloudformation-stack.sh; then
                log_success "Cleanup completed successfully"
                return 0
            else
                log_error "Cleanup failed"
                return 1
            fi
        else
            log_error "Cleanup script not found"
            return 1
        fi
    else
        log_info "No cleanup needed"
        return 0
    fi
}

# Deploy using CDK
deploy_cdk() {
    log_info "Starting CDK deployment..."
    
    # Change to infrastructure directory
    cd caseapp/infrastructure
    
    # Install Python dependencies
    log_info "Installing Python dependencies..."
    pip install -r ../requirements.txt
    
    # Bootstrap CDK if needed
    log_info "Bootstrapping CDK..."
    cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/$REGION
    
    # Synthesize the stack
    log_info "Synthesizing CDK stack..."
    cdk synth
    
    # Deploy the stack
    log_info "Deploying CDK stack..."
    cdk deploy --require-approval never --region $REGION
    
    cd ../..
    
    log_success "CDK deployment completed"
    return 0
}

# Deploy using direct CloudFormation
deploy_cloudformation() {
    log_info "Starting CloudFormation deployment..."
    
    # Generate CloudFormation template
    cd caseapp/infrastructure
    
    log_info "Generating CloudFormation template..."
    python3 -c "
import aws_cdk as cdk
from app import CourtCaseManagementStack

app = cdk.App()
stack = CourtCaseManagementStack(app, 'CourtCaseManagementStack')
template = app.synth().get_stack_by_name('CourtCaseManagementStack').template

import json
with open('template.json', 'w') as f:
    json.dump(template, f, indent=2)
"
    
    # Deploy using CloudFormation
    log_info "Deploying CloudFormation stack..."
    aws cloudformation create-stack \
        --stack-name "$STACK_NAME" \
        --template-body file://template.json \
        --capabilities CAPABILITY_IAM \
        --region "$REGION"
    
    # Wait for deployment to complete
    log_info "Waiting for stack creation to complete..."
    aws cloudformation wait stack-create-complete \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
    
    cd ../..
    
    log_success "CloudFormation deployment completed"
    return 0
}

# Attempt deployment with retry logic
attempt_deployment() {
    local attempt=$1
    
    log_info "Deployment attempt $attempt of $MAX_RETRIES"
    
    # Try CDK first, fall back to CloudFormation
    if command -v cdk &> /dev/null; then
        log_info "Using CDK for deployment"
        if deploy_cdk; then
            return 0
        else
            log_warning "CDK deployment failed, trying CloudFormation"
            if deploy_cloudformation; then
                return 0
            else
                return 1
            fi
        fi
    else
        log_info "CDK not available, using CloudFormation"
        if deploy_cloudformation; then
            return 0
        else
            return 1
        fi
    fi
}

# Validate deployment success
validate_deployment() {
    log_info "Validating deployment success..."
    
    # Check stack status
    local stack_status
    stack_status=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "STACK_NOT_FOUND")
    
    if [ "$stack_status" = "CREATE_COMPLETE" ] || [ "$stack_status" = "UPDATE_COMPLETE" ]; then
        log_success "Stack deployment successful: $stack_status"
    else
        log_error "Stack deployment failed: $stack_status"
        return 1
    fi
    
    # Check ECS service status
    log_info "Checking ECS service status..."
    local service_status
    service_status=$(aws ecs describe-services \
        --cluster CourtCaseCluster \
        --services BackendService \
        --region "$REGION" \
        --query 'services[0].status' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$service_status" = "ACTIVE" ]; then
        log_success "ECS service is active"
    else
        log_warning "ECS service status: $service_status"
    fi
    
    # Get stack outputs
    log_info "Retrieving stack outputs..."
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs' \
        --output table 2>/dev/null || log_warning "No stack outputs available"
    
    log_success "Deployment validation completed"
    return 0
}

# Main deployment function with retry logic
deploy_with_retry() {
    local attempt=1
    
    while [ $attempt -le $MAX_RETRIES ]; do
        log_info "=== Deployment Attempt $attempt ==="
        
        if attempt_deployment $attempt; then
            log_success "Deployment successful on attempt $attempt"
            
            if validate_deployment; then
                return 0
            else
                log_warning "Deployment validation failed"
            fi
        else
            log_error "Deployment attempt $attempt failed"
        fi
        
        if [ $attempt -lt $MAX_RETRIES ]; then
            local delay
            delay=$(calculate_delay $attempt)
            log_info "Waiting ${delay}s before retry..."
            sleep $delay
        fi
        
        attempt=$((attempt + 1))
    done
    
    log_error "All deployment attempts failed"
    return 1
}

# Main execution
main() {
    log_info "Starting comprehensive deployment process..."
    log_info "Stack: $STACK_NAME"
    log_info "Region: $REGION"
    log_info "Max Retries: $MAX_RETRIES"
    echo
    
    # Step 1: Run pre-deployment validation
    if ! run_validation; then
        log_error "Pre-deployment validation failed. Aborting deployment."
        exit 1
    fi
    
    echo
    
    # Step 2: Run cleanup if needed
    if ! run_cleanup; then
        log_error "Cleanup failed. Aborting deployment."
        exit 1
    fi
    
    echo
    
    # Step 3: Deploy with retry logic
    if deploy_with_retry; then
        log_success "🎉 Deployment completed successfully!"
        echo
        log_info "Next steps:"
        log_info "1. Check the application at the load balancer URL"
        log_info "2. Monitor ECS service health in the AWS console"
        log_info "3. Review CloudWatch logs for any issues"
        exit 0
    else
        log_error "❌ Deployment failed after $MAX_RETRIES attempts"
        echo
        log_info "Troubleshooting steps:"
        log_info "1. Check CloudFormation events: aws cloudformation describe-stack-events --stack-name $STACK_NAME"
        log_info "2. Check ECS service logs in CloudWatch"
        log_info "3. Verify Docker images are accessible"
        log_info "4. Run cleanup script and try again"
        exit 1
    fi
}

# Handle script interruption
trap 'log_error "Deployment interrupted by user"; exit 1' INT TERM

# Execute main function
main "$@"