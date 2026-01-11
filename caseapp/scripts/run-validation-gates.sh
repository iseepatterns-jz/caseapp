#!/bin/zsh

# Deployment Validation Gates Integration Script
# This script provides a simple interface to run validation gates from other scripts

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${0}")" && pwd)"
VALIDATION_SCRIPT="${SCRIPT_DIR}/deployment-validation-gates.sh"

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

# Show usage
show_usage() {
    echo "Deployment Validation Gates Integration Script"
    echo "============================================="
    echo
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  --strict          Fail on warnings (default: warnings are allowed)"
    echo "  --docker-only     Run only Docker image validation"
    echo "  --aws-only        Run only AWS service validation"
    echo "  --prereq-only     Run only prerequisite validation"
    echo "  --help, -h        Show this help message"
    echo
    echo "Environment Variables:"
    echo "  DOCKER_USERNAME   Docker Hub username (default: iseepatterns)"
    echo "  AWS_REGION        AWS region (default: us-east-1)"
    echo
    echo "Exit Codes:"
    echo "  0 - All gates passed (or warnings in non-strict mode)"
    echo "  1 - Warnings found (only in strict mode)"
    echo "  2 - One or more gates failed"
    echo
}

# Run validation gates
run_validation_gates() {
    local strict_mode=false
    local validation_type="all"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --strict)
                strict_mode=true
                shift
                ;;
            --docker-only)
                validation_type="docker"
                shift
                ;;
            --aws-only)
                validation_type="aws"
                shift
                ;;
            --prereq-only)
                validation_type="prereq"
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Check if validation script exists
    if [ ! -f "$VALIDATION_SCRIPT" ]; then
        log_error "Validation script not found: $VALIDATION_SCRIPT"
        return 2
    fi
    
    # Make script executable
    chmod +x "$VALIDATION_SCRIPT"
    
    log_info "Running deployment validation gates..."
    log_info "Strict mode: $strict_mode"
    log_info "Validation type: $validation_type"
    echo
    
    # Run the validation script
    if [ "$validation_type" = "all" ]; then
        # Run full validation
        "$VALIDATION_SCRIPT"
        local exit_code=$?
    else
        # For specific validation types, we'll need to modify the main script
        # For now, run full validation and note the limitation
        log_warning "Specific validation types not yet implemented, running full validation"
        "$VALIDATION_SCRIPT"
        local exit_code=$?
    fi
    
    # Handle results based on strict mode
    case $exit_code in
        0)
            log_success "🎉 All validation gates passed!"
            return 0
            ;;
        1)
            if [ "$strict_mode" = true ]; then
                log_error "❌ Validation gates completed with warnings (strict mode enabled)"
                return 1
            else
                log_warning "⚠️  Validation gates completed with warnings (proceeding in non-strict mode)"
                return 0
            fi
            ;;
        2)
            log_error "❌ One or more validation gates failed"
            return 2
            ;;
        *)
            log_error "❌ Validation script returned unexpected exit code: $exit_code"
            return 2
            ;;
    esac
}

# Main execution
main() {
    # Check if help is requested
    if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
        show_usage
        exit 0
    fi
    
    # Run validation gates with provided arguments
    run_validation_gates "$@"
}

# Execute main function
main "$@"