#!/bin/bash

# AWS Deployment Script for Court Case Management System
set -e

echo "🚀 Starting AWS deployment for Court Case Management System..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
STACK_NAME="CourtCaseManagementStack"
ENVIRONMENT=${ENVIRONMENT:-production}

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Python
    if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
        print_error "Python is not installed. Please install Python 3.11+."
        exit 1
    fi
    
    # Check pip
    if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
        print_error "pip is not installed. Please install pip."
        exit 1
    fi
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check CDK CLI
    if ! command -v cdk &> /dev/null; then
        print_error "AWS CDK CLI is not installed. Please install it first: npm install -g aws-cdk"
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Please run 'aws configure'."
        exit 1
    fi
    
    print_status "Prerequisites check passed ✅"
}

# Run tests
run_tests() {
    print_status "Running tests..."
    
    # Backend tests
    cd backend
    if ! python -m pytest tests/ -v; then
        print_error "Backend tests failed. Please fix before deploying."
        exit 1
    fi
    cd ..
    
    print_status "All tests passed ✅"
}

# Build Docker images
build_images() {
    print_status "Building Docker images..."
    
    # Build backend image
    docker build -t court-case-backend:latest --target backend-base .
    
    # Build frontend image
    docker build -t court-case-frontend:latest --target frontend .
    
    # Build media processor image
    docker build -t court-case-media:latest --target media-processor .
    
    print_status "Docker images built successfully ✅"
}

# Bootstrap CDK (if needed)
bootstrap_cdk() {
    print_status "Checking CDK bootstrap status..."
    
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    
    # Check if already bootstrapped
    if aws cloudformation describe-stacks --stack-name CDKToolkit --region $AWS_REGION &> /dev/null; then
        print_status "CDK already bootstrapped ✅"
    else
        print_status "Bootstrapping CDK..."
        cd infrastructure
        
        # Install Python dependencies first
        print_status "Installing Python CDK dependencies..."
        pip install -r requirements.txt
        
        # Install Node.js dependencies for CLI
        print_status "Installing Node.js CDK CLI dependencies..."
        npm install
        
        # Bootstrap
        cdk bootstrap aws://$ACCOUNT_ID/$AWS_REGION
        cd ..
        print_status "CDK bootstrapped successfully ✅"
    fi
}

# Deploy infrastructure
deploy_infrastructure() {
    print_status "Deploying infrastructure..."
    
    cd infrastructure
    
    # Install Python dependencies
    print_status "Installing Python CDK dependencies..."
    pip install -r requirements.txt
    
    # Install Node.js dependencies for CLI
    print_status "Installing Node.js CDK CLI dependencies..."
    npm install
    
    # Synthesize CloudFormation template
    print_status "Synthesizing CDK app..."
    cdk synth
    
    # Deploy the stack
    print_status "Deploying CDK stack..."
    cdk deploy $STACK_NAME --require-approval never
    
    cd ..
    
    print_status "Infrastructure deployed successfully ✅"
}

# Get deployment outputs
get_outputs() {
    print_status "Retrieving deployment outputs..."
    
    # Get stack outputs
    OUTPUTS=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $AWS_REGION \
        --query 'Stacks[0].Outputs' \
        --output json)
    
    echo "$OUTPUTS" > deployment-outputs.json
    
    # Extract key values
    ALB_DNS=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="LoadBalancerDNS") | .OutputValue')
    DB_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="DatabaseEndpoint") | .OutputValue')
    
    print_status "Application URL: http://$ALB_DNS"
    print_status "Database Endpoint: $DB_ENDPOINT"
    print_status "Outputs saved to deployment-outputs.json ✅"
}

# Run database migrations
run_migrations() {
    print_status "Running database migrations..."
    
    # This would typically be done via ECS task or Lambda
    print_warning "Database migrations should be run manually after deployment"
    print_warning "Connect to the ECS cluster and run: alembic upgrade head"
}

# Validate deployment
validate_deployment() {
    print_status "Validating deployment..."
    
    # Get ALB DNS name
    ALB_DNS=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $AWS_REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' \
        --output text)
    
    # Check health endpoint
    if curl -f "http://$ALB_DNS/health" &> /dev/null; then
        print_status "Health check passed ✅"
    else
        print_warning "Health check failed. Application may still be starting up."
    fi
    
    # Check API documentation
    if curl -f "http://$ALB_DNS/docs" &> /dev/null; then
        print_status "API documentation accessible ✅"
    else
        print_warning "API documentation not accessible yet."
    fi
}

# Cleanup function
cleanup() {
    print_status "Cleaning up temporary files..."
    # Add any cleanup tasks here
}

# Main deployment flow
main() {
    print_status "Starting deployment process..."
    
    # Set trap for cleanup
    trap cleanup EXIT
    
    # Run deployment steps
    check_prerequisites
    run_tests
    build_images
    bootstrap_cdk
    deploy_infrastructure
    get_outputs
    run_migrations
    validate_deployment
    
    print_status "🎉 Deployment completed successfully!"
    print_status "Next steps:"
    echo "  1. Run database migrations"
    echo "  2. Create initial admin user"
    echo "  3. Configure domain name (optional)"
    echo "  4. Set up monitoring and alerts"
    echo "  5. Test all functionality"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "destroy")
        print_warning "Destroying infrastructure..."
        cd infrastructure
        cdk destroy $STACK_NAME
        cd ..
        print_status "Infrastructure destroyed ✅"
        ;;
    "diff")
        print_status "Showing infrastructure diff..."
        cd infrastructure
        cdk diff $STACK_NAME
        cd ..
        ;;
    "outputs")
        get_outputs
        ;;
    *)
        echo "Usage: $0 [deploy|destroy|diff|outputs]"
        echo "  deploy  - Deploy the application (default)"
        echo "  destroy - Destroy the infrastructure"
        echo "  diff    - Show infrastructure changes"
        echo "  outputs - Get deployment outputs"
        exit 1
        ;;
esac