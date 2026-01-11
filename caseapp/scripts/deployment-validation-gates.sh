#!/bin/zsh

# Deployment Validation Gates Script
# Comprehensive validation gates for deployment pipeline

# Configuration
REGION="${AWS_REGION:-us-east-1}"
DOCKER_USERNAME="${DOCKER_USERNAME:-iseepatterns}"
REQUIRED_SERVICES=("ecs" "rds" "s3" "cloudformation" "ec2")

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

log_gate() {
    echo -e "${CYAN}[GATE]${NC} $1"
}

# Gate 1: Docker Image Accessibility Validation
validate_docker_images() {
    log_gate "Gate 1: Validating Docker image accessibility..."
    
    local images=(
        "${DOCKER_USERNAME}/court-case-backend:latest"
        "${DOCKER_USERNAME}/court-case-media:latest"
    )
    
    local all_accessible=true
    
    for image in "${images[@]}"; do
        log_info "Checking image: $image"
        
        # Check if Docker is available
        if ! command -v docker &>/dev/null; then
            log_warning "⚠️  Docker not available, skipping image validation"
            continue
        fi
        
        # Check if image exists and is accessible
        if docker manifest inspect "$image" &>/dev/null; then
            log_success "✅ Image accessible: $image"
        else
            log_error "❌ Image not accessible: $image"
            all_accessible=false
        fi
    done
    
    if [ "$all_accessible" = true ]; then
        log_success "🎉 Gate 1 PASSED: All Docker images are accessible"
        return 0
    else
        log_error "❌ Gate 1 FAILED: Some Docker images are not accessible"
        return 1
    fi
}

# Gate 2: AWS Service Availability Validation
validate_aws_services() {
    log_gate "Gate 2: Validating AWS service availability..."
    
    # Check AWS CLI configuration
    if ! command -v aws &>/dev/null; then
        log_error "❌ AWS CLI not installed"
        return 1
    fi
    
    if ! aws sts get-caller-identity &>/dev/null; then
        log_error "❌ AWS CLI not configured or credentials invalid"
        return 1
    fi
    
    local account_id
    account_id=$(aws sts get-caller-identity --query Account --output text)
    log_info "AWS Account: $account_id"
    
    local all_available=true
    
    # Check each required service
    for service in "${REQUIRED_SERVICES[@]}"; do
        log_info "Checking $service service availability..."
        
        case "$service" in
            "ecs")
                if aws ecs list-clusters --region "$REGION" --max-items 1 &>/dev/null; then
                    log_success "✅ ECS service available"
                else
                    log_error "❌ ECS service not available"
                    all_available=false
                fi
                ;;
            "rds")
                if aws rds describe-db-instances --region "$REGION" --max-items 1 &>/dev/null; then
                    log_success "✅ RDS service available"
                else
                    log_error "❌ RDS service not available"
                    all_available=false
                fi
                ;;
            "s3")
                if aws s3 ls &>/dev/null; then
                    log_success "✅ S3 service available"
                else
                    log_error "❌ S3 service not available"
                    all_available=false
                fi
                ;;
            "cloudformation")
                if aws cloudformation list-stacks --region "$REGION" --max-items 1 &>/dev/null; then
                    log_success "✅ CloudFormation service available"
                else
                    log_error "❌ CloudFormation service not available"
                    all_available=false
                fi
                ;;
            "ec2")
                if aws ec2 describe-vpcs --region "$REGION" --max-items 1 &>/dev/null; then
                    log_success "✅ EC2 service available"
                else
                    log_error "❌ EC2 service not available"
                    all_available=false
                fi
                ;;
        esac
    done
    
    if [ "$all_available" = true ]; then
        log_success "🎉 Gate 2 PASSED: All AWS services are available"
        return 0
    else
        log_error "❌ Gate 2 FAILED: Some AWS services are not available"
        return 1
    fi
}

# Gate 3: Deployment Prerequisites Validation
validate_deployment_prerequisites() {
    log_gate "Gate 3: Validating deployment prerequisites..."
    
    local prerequisites_ok=true
    
    # Check if required tools are installed
    local required_tools=("python3" "pip" "curl")
    
    for tool in "${required_tools[@]}"; do
        if command -v "$tool" &>/dev/null; then
            local version
            case "$tool" in
                "python3")
                    version=$(python3 --version 2>&1)
                    ;;
                "pip")
                    version=$(pip --version 2>&1 | head -n1)
                    ;;
                "curl")
                    version=$(curl --version 2>&1 | head -n1)
                    ;;
            esac
            log_success "✅ $tool available: $version"
        else
            log_error "❌ $tool not found"
            prerequisites_ok=false
        fi
    done
    
    # Check if required files exist
    local required_files=(
        "infrastructure/app.py"
        "requirements.txt"
        "Dockerfile"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            log_success "✅ Required file exists: $file"
        else
            log_error "❌ Required file missing: $file"
            prerequisites_ok=false
        fi
    done
    
    if [ "$prerequisites_ok" = true ]; then
        log_success "🎉 Gate 3 PASSED: All deployment prerequisites are satisfied"
        return 0
    else
        log_error "❌ Gate 3 FAILED: Missing deployment prerequisites"
        return 1
    fi
}

# Generate validation report
generate_validation_report() {
    local overall_status="$1"
    local failed_gates="$2"
    
    echo
    echo "=================================="
    echo "DEPLOYMENT VALIDATION GATES REPORT"
    echo "=================================="
    echo "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    echo "Region: $REGION"
    echo "Docker Username: $DOCKER_USERNAME"
    echo
    
    echo "GATE RESULTS:"
    echo "============="
    echo "Gate 1 - Docker Image Accessibility: $([ "${failed_gates}" != *"1"* ] && echo "✅ PASSED" || echo "❌ FAILED")"
    echo "Gate 2 - AWS Service Availability: $([ "${failed_gates}" != *"2"* ] && echo "✅ PASSED" || echo "❌ FAILED")"
    echo "Gate 3 - Deployment Prerequisites: $([ "${failed_gates}" != *"3"* ] && echo "✅ PASSED" || echo "❌ FAILED")"
    echo
    
    echo "OVERALL STATUS: $overall_status"
    echo
    
    case "$overall_status" in
        "PASSED")
            log_success "🎉 All validation gates passed! Deployment can proceed."
            echo "✅ The deployment pipeline is ready to execute."
            ;;
        "WARNING")
            log_warning "⚠️  Some validation gates have warnings."
            echo "⚠️  Review the warnings above. Deployment may proceed with caution."
            ;;
        "FAILED")
            log_error "❌ One or more validation gates failed."
            echo "❌ Deployment should NOT proceed until issues are resolved."
            ;;
    esac
    echo
}

# Main execution function
main() {
    echo
    log_info "Starting Deployment Validation Gates..."
    echo "======================================"
    
    local failed_gates=""
    local overall_status="PASSED"
    
    # Execute all validation gates
    if ! validate_docker_images; then
        failed_gates="${failed_gates}1 "
        overall_status="FAILED"
    fi
    echo
    
    if ! validate_aws_services; then
        failed_gates="${failed_gates}2 "
        overall_status="FAILED"
    fi
    echo
    
    if ! validate_deployment_prerequisites; then
        failed_gates="${failed_gates}3 "
        overall_status="FAILED"
    fi
    echo
    
    # Generate final report
    generate_validation_report "$overall_status" "$failed_gates"
    
    # Exit with appropriate code
    case "$overall_status" in
        "PASSED")
            exit 0
            ;;
        "WARNING")
            exit 1  # Warning status - let caller decide
            ;;
        "FAILED")
            exit 2  # Hard failure
            ;;
    esac
}

# Show help
show_help() {
    echo "Deployment Validation Gates Script"
    echo "=================================="
    echo
    echo "This script validates deployment prerequisites and environment readiness."
    echo
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo
    echo "Environment Variables:"
    echo "  DOCKER_USERNAME    Docker Hub username (default: iseepatterns)"
    echo "  AWS_REGION         AWS region (default: us-east-1)"
    echo
    echo "Exit Codes:"
    echo "  0 - All gates passed"
    echo "  1 - Some gates have warnings"
    echo "  2 - One or more gates failed"
    echo
}

# Script entry point
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    show_help
    exit 0
fi

# Run main function
main "$@"