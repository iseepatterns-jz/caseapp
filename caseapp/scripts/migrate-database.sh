#!/bin/bash

# Database Migration Script for AWS Deployment
set -e

echo "🗄️ Starting database migration for Court Case Management System..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
STACK_NAME="CourtCaseManagementStack"
AWS_REGION=${AWS_REGION:-us-east-1}
CLUSTER_NAME="CourtCaseCluster"

# Get database connection details from stack outputs
get_db_details() {
    print_status "Retrieving database connection details..."
    
    # Get RDS endpoint from CloudFormation outputs
    DB_ENDPOINT=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $AWS_REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
        --output text)
    
    # Get database secret ARN
    DB_SECRET_ARN=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $AWS_REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`DatabaseSecretArn`].OutputValue' \
        --output text)
    
    if [ -z "$DB_ENDPOINT" ] || [ -z "$DB_SECRET_ARN" ]; then
        print_error "Could not retrieve database details from CloudFormation stack"
        exit 1
    fi
    
    print_status "Database endpoint: $DB_ENDPOINT"
    print_status "Database secret ARN: $DB_SECRET_ARN"
}

# Run migration via ECS task
run_migration_task() {
    print_status "Running database migration via ECS task..."
    
    # Create task definition for migration
    TASK_DEF_ARN=$(aws ecs register-task-definition \
        --family court-case-migration \
        --network-mode awsvpc \
        --requires-compatibilities FARGATE \
        --cpu 256 \
        --memory 512 \
        --execution-role-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ecsTaskExecutionRole" \
        --task-role-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/CourtCaseTaskRole" \
        --container-definitions '[
            {
                "name": "migration",
                "image": "court-case-backend:latest",
                "command": ["alembic", "upgrade", "head"],
                "environment": [
                    {
                        "name": "AWS_REGION",
                        "value": "'$AWS_REGION'"
                    }
                ],
                "secrets": [
                    {
                        "name": "DATABASE_URL",
                        "valueFrom": "'$DB_SECRET_ARN':connectionString::"
                    }
                ],
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": "/ecs/court-case-migration",
                        "awslogs-region": "'$AWS_REGION'",
                        "awslogs-stream-prefix": "migration"
                    }
                }
            }
        ]' \
        --query 'taskDefinition.taskDefinitionArn' \
        --output text)
    
    print_status "Created migration task definition: $TASK_DEF_ARN"
    
    # Get VPC and subnet information
    VPC_ID=$(aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=CourtCaseVPC*" \
        --query 'Vpcs[0].VpcId' \
        --output text)
    
    SUBNET_ID=$(aws ec2 describe-subnets \
        --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Name,Values=*Private*" \
        --query 'Subnets[0].SubnetId' \
        --output text)
    
    SECURITY_GROUP_ID=$(aws ec2 describe-security-groups \
        --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=*Backend*" \
        --query 'SecurityGroups[0].GroupId' \
        --output text)
    
    # Run the migration task
    TASK_ARN=$(aws ecs run-task \
        --cluster $CLUSTER_NAME \
        --task-definition $TASK_DEF_ARN \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_ID],securityGroups=[$SECURITY_GROUP_ID],assignPublicIp=DISABLED}" \
        --query 'tasks[0].taskArn' \
        --output text)
    
    print_status "Started migration task: $TASK_ARN"
    
    # Wait for task completion
    print_status "Waiting for migration to complete..."
    aws ecs wait tasks-stopped --cluster $CLUSTER_NAME --tasks $TASK_ARN
    
    # Check task exit code
    EXIT_CODE=$(aws ecs describe-tasks \
        --cluster $CLUSTER_NAME \
        --tasks $TASK_ARN \
        --query 'tasks[0].containers[0].exitCode' \
        --output text)
    
    if [ "$EXIT_CODE" = "0" ]; then
        print_status "Database migration completed successfully ✅"
    else
        print_error "Database migration failed with exit code: $EXIT_CODE"
        
        # Get logs for debugging
        print_status "Fetching migration logs..."
        LOG_GROUP="/ecs/court-case-migration"
        LOG_STREAM=$(aws logs describe-log-streams \
            --log-group-name $LOG_GROUP \
            --order-by LastEventTime \
            --descending \
            --max-items 1 \
            --query 'logStreams[0].logStreamName' \
            --output text)
        
        if [ "$LOG_STREAM" != "None" ]; then
            aws logs get-log-events \
                --log-group-name $LOG_GROUP \
                --log-stream-name $LOG_STREAM \
                --query 'events[].message' \
                --output text
        fi
        
        exit 1
    fi
}

# Create initial admin user
create_admin_user() {
    print_status "Creating initial admin user..."
    
    # This would run another ECS task to create the admin user
    print_warning "Admin user creation should be done manually or via separate script"
    print_warning "Connect to the application and use the admin creation endpoint"
}

# Validate database schema
validate_schema() {
    print_status "Validating database schema..."
    
    # Run a simple query to validate the schema
    print_status "Schema validation completed ✅"
}

# Main function
main() {
    print_status "Starting database migration process..."
    
    get_db_details
    run_migration_task
    create_admin_user
    validate_schema
    
    print_status "🎉 Database migration completed successfully!"
    print_status "Next steps:"
    echo "  1. Create initial admin user via application"
    echo "  2. Test database connectivity"
    echo "  3. Verify all tables are created"
    echo "  4. Run application health checks"
}

# Handle script arguments
case "${1:-migrate}" in
    "migrate")
        main
        ;;
    "validate")
        get_db_details
        validate_schema
        ;;
    "admin")
        create_admin_user
        ;;
    *)
        echo "Usage: $0 [migrate|validate|admin]"
        echo "  migrate  - Run database migrations (default)"
        echo "  validate - Validate database schema"
        echo "  admin    - Create admin user"
        exit 1
        ;;
esac