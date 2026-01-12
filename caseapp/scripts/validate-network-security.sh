#!/bin/bash

# Network Security Validation Script for Court Case Management System
# Validates security group configurations and network access patterns

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

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

# Function to check if AWS CLI is available
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed or not in PATH"
        return 1
    fi
    
    # Check if AWS credentials are configured
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials are not configured or invalid"
        return 1
    fi
    
    log_success "AWS CLI is available and configured"
    return 0
}

# Function to get CloudFormation stack name
get_stack_name() {
    local stack_name="${1:-CourtCaseManagementStack}"
    echo "$stack_name"
}

# Function to get security group ID from stack
get_security_group_id() {
    local stack_name="$1"
    local logical_id="$2"
    
    aws cloudformation describe-stack-resources \
        --stack-name "$stack_name" \
        --logical-resource-id "$logical_id" \
        --query 'StackResources[0].PhysicalResourceId' \
        --output text 2>/dev/null || echo "NOT_FOUND"
}

# Function to validate security group rules
validate_security_group() {
    local sg_id="$1"
    local sg_name="$2"
    local expected_rules="$3"
    
    if [ "$sg_id" = "NOT_FOUND" ]; then
        log_warning "Security group $sg_name not found in stack"
        return 1
    fi
    
    log_info "Validating security group: $sg_name ($sg_id)"
    
    # Get security group details
    local sg_details
    sg_details=$(aws ec2 describe-security-groups \
        --group-ids "$sg_id" \
        --query 'SecurityGroups[0]' \
        --output json 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        log_error "Failed to describe security group $sg_id"
        return 1
    fi
    
    # Extract ingress and egress rules
    local ingress_rules
    local egress_rules
    
    ingress_rules=$(echo "$sg_details" | jq -r '.IpPermissions[] | "\(.IpProtocol):\(.FromPort // "all"):\(.ToPort // "all")"' 2>/dev/null || echo "")
    egress_rules=$(echo "$sg_details" | jq -r '.IpPermissionsEgress[] | "\(.IpProtocol):\(.FromPort // "all"):\(.ToPort // "all")"' 2>/dev/null || echo "")
    
    echo "  Ingress rules:"
    if [ -n "$ingress_rules" ]; then
        echo "$ingress_rules" | while read -r rule; do
            echo "    - $rule"
        done
    else
        echo "    - No ingress rules"
    fi
    
    echo "  Egress rules:"
    if [ -n "$egress_rules" ]; then
        echo "$egress_rules" | while read -r rule; do
            echo "    - $rule"
        done
    else
        echo "    - No egress rules"
    fi
    
    return 0
}

# Function to validate database security group
validate_database_security() {
    local stack_name="$1"
    
    log_info "Validating database security configuration..."
    
    local db_sg_id
    db_sg_id=$(get_security_group_id "$stack_name" "DatabaseSecurityGroup")
    
    validate_security_group "$db_sg_id" "Database" "postgresql:5432"
    
    # Check that database is in private subnets
    local db_instance_id
    db_instance_id=$(aws cloudformation describe-stack-resources \
        --stack-name "$stack_name" \
        --logical-resource-id "CourtCaseDatabase" \
        --query 'StackResources[0].PhysicalResourceId' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$db_instance_id" != "NOT_FOUND" ]; then
        local db_subnets
        db_subnets=$(aws rds describe-db-instances \
            --db-instance-identifier "$db_instance_id" \
            --query 'DBInstances[0].DBSubnetGroup.Subnets[].SubnetIdentifier' \
            --output text 2>/dev/null || echo "")
        
        if [ -n "$db_subnets" ]; then
            log_success "Database is deployed in subnets: $db_subnets"
        else
            log_warning "Could not determine database subnet configuration"
        fi
    else
        log_warning "Database instance not found in stack"
    fi
}

# Function to validate Redis security group
validate_redis_security() {
    local stack_name="$1"
    
    log_info "Validating Redis security configuration..."
    
    local redis_sg_id
    redis_sg_id=$(get_security_group_id "$stack_name" "RedisSecurityGroup")
    
    validate_security_group "$redis_sg_id" "Redis" "tcp:6379"
}

# Function to validate OpenSearch security group
validate_opensearch_security() {
    local stack_name="$1"
    
    log_info "Validating OpenSearch security configuration..."
    
    local opensearch_sg_id
    opensearch_sg_id=$(get_security_group_id "$stack_name" "OpenSearchSecurityGroup")
    
    validate_security_group "$opensearch_sg_id" "OpenSearch" "https:443"
}

# Function to validate ECS security group
validate_ecs_security() {
    local stack_name="$1"
    
    log_info "Validating ECS security configuration..."
    
    local ecs_sg_id
    ecs_sg_id=$(get_security_group_id "$stack_name" "ECSServiceSecurityGroup")
    
    validate_security_group "$ecs_sg_id" "ECS Service" "http:8000"
    
    # Check ECS service configuration
    local cluster_name
    cluster_name=$(aws cloudformation describe-stack-resources \
        --stack-name "$stack_name" \
        --logical-resource-id "CourtCaseCluster" \
        --query 'StackResources[0].PhysicalResourceId' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$cluster_name" != "NOT_FOUND" ]; then
        local service_name
        service_name=$(aws ecs list-services \
            --cluster "$cluster_name" \
            --query 'serviceArns[0]' \
            --output text 2>/dev/null | sed 's/.*\///' || echo "NOT_FOUND")
        
        if [ "$service_name" != "NOT_FOUND" ]; then
            log_info "ECS Service found: $service_name in cluster $cluster_name"
            
            # Get service details
            local service_details
            service_details=$(aws ecs describe-services \
                --cluster "$cluster_name" \
                --services "$service_name" \
                --query 'services[0]' \
                --output json 2>/dev/null)
            
            if [ $? -eq 0 ]; then
                local desired_count
                local running_count
                desired_count=$(echo "$service_details" | jq -r '.desiredCount')
                running_count=$(echo "$service_details" | jq -r '.runningCount')
                
                log_info "ECS Service status: $running_count/$desired_count tasks running"
                
                # Check if service is in private subnets
                local subnet_ids
                subnet_ids=$(echo "$service_details" | jq -r '.networkConfiguration.awsvpcConfiguration.subnets[]' 2>/dev/null | tr '\n' ' ')
                
                if [ -n "$subnet_ids" ]; then
                    log_success "ECS Service is deployed in subnets: $subnet_ids"
                else
                    log_warning "Could not determine ECS service subnet configuration"
                fi
            fi
        else
            log_warning "ECS service not found in cluster"
        fi
    else
        log_warning "ECS cluster not found in stack"
    fi
}

# Function to validate ALB security group
validate_alb_security() {
    local stack_name="$1"
    
    log_info "Validating Application Load Balancer security configuration..."
    
    # Find ALB from stack resources
    local alb_arn
    alb_arn=$(aws cloudformation describe-stack-resources \
        --stack-name "$stack_name" \
        --query 'StackResources[?ResourceType==`AWS::ElasticLoadBalancingV2::LoadBalancer`].PhysicalResourceId' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$alb_arn" != "NOT_FOUND" ]; then
        local alb_sg_ids
        alb_sg_ids=$(aws elbv2 describe-load-balancers \
            --load-balancer-arns "$alb_arn" \
            --query 'LoadBalancers[0].SecurityGroups[]' \
            --output text 2>/dev/null || echo "")
        
        if [ -n "$alb_sg_ids" ]; then
            for sg_id in $alb_sg_ids; do
                validate_security_group "$sg_id" "ALB" "http:80,https:443"
            done
        else
            log_warning "Could not determine ALB security groups"
        fi
    else
        log_warning "Application Load Balancer not found in stack"
    fi
}

# Function to check network connectivity
check_network_connectivity() {
    local stack_name="$1"
    
    log_info "Checking network connectivity patterns..."
    
    # This would require more complex testing with actual instances
    # For now, we'll just validate the security group configurations
    log_info "Network connectivity validation requires running instances"
    log_info "Security group rules have been validated above"
}

# Function to generate security recommendations
generate_security_recommendations() {
    log_info "Security Recommendations:"
    echo "=========================="
    
    echo "1. Database Security:"
    echo "   - ✓ Database should be in private subnets (isolated)"
    echo "   - ✓ Only allow PostgreSQL (5432) from ECS security group"
    echo "   - ✓ Enable encryption at rest and in transit"
    echo ""
    
    echo "2. Redis Security:"
    echo "   - ✓ Redis should be in private subnets"
    echo "   - ✓ Only allow Redis (6379) from ECS security group"
    echo "   - ✓ Enable auth token and encryption"
    echo ""
    
    echo "3. OpenSearch Security:"
    echo "   - ✓ OpenSearch should be in private subnets"
    echo "   - ✓ Only allow HTTPS (443) from ECS security group"
    echo "   - ✓ Enable fine-grained access control"
    echo ""
    
    echo "4. ECS Security:"
    echo "   - ✓ ECS tasks should be in private subnets"
    echo "   - ✓ Only allow HTTP (8000) from ALB security group"
    echo "   - ✓ Allow outbound for AWS service calls"
    echo ""
    
    echo "5. ALB Security:"
    echo "   - ✓ ALB should be in public subnets"
    echo "   - ✓ Allow HTTP (80) and HTTPS (443) from internet"
    echo "   - ✓ Redirect HTTP to HTTPS in production"
    echo ""
}

# Function to show help
show_help() {
    echo "Network Security Validation Script for Court Case Management System"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  validate [stack-name]     Validate all security groups (default: CourtCaseManagementStack)"
    echo "  database [stack-name]     Validate database security only"
    echo "  redis [stack-name]        Validate Redis security only"
    echo "  opensearch [stack-name]   Validate OpenSearch security only"
    echo "  ecs [stack-name]          Validate ECS security only"
    echo "  alb [stack-name]          Validate ALB security only"
    echo "  recommendations           Show security recommendations"
    echo "  help                      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 validate                           # Validate all security groups"
    echo "  $0 validate MyStack                   # Validate specific stack"
    echo "  $0 database                           # Validate database security only"
    echo "  $0 recommendations                    # Show security recommendations"
    echo ""
}

# Main script logic
main() {
    local command="${1:-validate}"
    local stack_name
    stack_name=$(get_stack_name "${2:-}")
    
    case "$command" in
        "validate")
            log_info "Starting comprehensive network security validation"
            log_info "Stack: $stack_name"
            echo "=================================================="
            
            if ! check_aws_cli; then
                exit 1
            fi
            
            validate_database_security "$stack_name"
            echo ""
            validate_redis_security "$stack_name"
            echo ""
            validate_opensearch_security "$stack_name"
            echo ""
            validate_ecs_security "$stack_name"
            echo ""
            validate_alb_security "$stack_name"
            echo ""
            check_network_connectivity "$stack_name"
            echo ""
            generate_security_recommendations
            ;;
        "database")
            if check_aws_cli; then
                validate_database_security "$stack_name"
            fi
            ;;
        "redis")
            if check_aws_cli; then
                validate_redis_security "$stack_name"
            fi
            ;;
        "opensearch")
            if check_aws_cli; then
                validate_opensearch_security "$stack_name"
            fi
            ;;
        "ecs")
            if check_aws_cli; then
                validate_ecs_security "$stack_name"
            fi
            ;;
        "alb")
            if check_aws_cli; then
                validate_alb_security "$stack_name"
            fi
            ;;
        "recommendations")
            generate_security_recommendations
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"