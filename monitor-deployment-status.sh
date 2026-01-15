#!/bin/bash

# Monitor deployment status with periodic checks
STACK_NAME="CourtCaseManagementStack"
CLUSTER="CourtCaseManagementStack-CourtCaseCluster9415FFD8-HbJFyEfiwG26"
SERVICE="CourtCaseManagementStack-BackendService2147DAF9-4XRMtP32fGqU"
TARGET_GROUP="arn:aws:elasticloadbalancing:us-east-1:730335557645:targetgroup/CourtC-Backe-I2CMVPPZHHZG/12ffa1f67cc77284"

export AWS_PAGER=""

echo "=== Starting Deployment Monitoring ==="
echo "Time: $(date)"
echo ""

for i in {1..20}; do
    echo "=== Check #$i at $(date) ==="
    
    # Check CloudFormation stack status
    STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].StackStatus' --output text 2>/dev/null)
    echo "Stack Status: $STACK_STATUS"
    
    # Check ECS service
    SERVICE_INFO=$(aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" --query 'services[0].{Running:runningCount,Desired:desiredCount,Pending:pendingCount}' --output json 2>/dev/null)
    echo "ECS Service: $SERVICE_INFO"
    
    # Check target health
    HEALTH=$(aws elbv2 describe-target-health --target-group-arn "$TARGET_GROUP" --query 'TargetHealthDescriptions[*].TargetHealth.State' --output json 2>/dev/null)
    echo "Target Health: $HEALTH"
    
    # Check for completion
    if [ "$STACK_STATUS" = "CREATE_COMPLETE" ]; then
        echo "✅ Stack creation COMPLETE!"
        exit 0
    elif [ "$STACK_STATUS" = "CREATE_FAILED" ] || [ "$STACK_STATUS" = "ROLLBACK_IN_PROGRESS" ] || [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ]; then
        echo "❌ Stack creation FAILED: $STACK_STATUS"
        exit 1
    fi
    
    echo ""
    sleep 120  # Check every 2 minutes
done

echo "⏱️ Monitoring timeout after 40 minutes"
