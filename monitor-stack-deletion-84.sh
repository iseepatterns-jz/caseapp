#!/bin/bash

echo "=== Stack Deletion Monitor for Deployment #84 ==="
echo "Started: $(date)"
echo ""

STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"
CHECK_INTERVAL=120  # Check every 2 minutes
MAX_CHECKS=15       # 30 minutes max

for i in $(seq 1 $MAX_CHECKS); do
    echo "[Check $i/$(MAX_CHECKS)] $(date +%H:%M:%S)"
    
    # Check stack status
    STACK_STATUS=$(AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>&1)
    
    if echo "$STACK_STATUS" | grep -q "does not exist"; then
        echo "✅ Stack deleted successfully!"
        echo "Deletion completed at: $(date)"
        exit 0
    fi
    
    echo "Status: $STACK_STATUS"
    
    # Show remaining resources
    REMAINING=$(AWS_PAGER="" aws cloudformation describe-stack-resources \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'StackResources[?ResourceStatus!=`DELETE_COMPLETE`].[LogicalResourceId,ResourceType,ResourceStatus]' \
        --output text 2>&1 | wc -l)
    
    echo "Remaining resources: $REMAINING"
    
    # Show what's currently deleting
    echo "Currently deleting:"
    AWS_PAGER="" aws cloudformation describe-stack-resources \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'StackResources[?ResourceStatus==`DELETE_IN_PROGRESS`].[LogicalResourceId,ResourceType]' \
        --output table 2>&1 | head -20
    
    echo ""
    
    if [ $i -lt $MAX_CHECKS ]; then
        echo "Waiting $CHECK_INTERVAL seconds..."
        sleep $CHECK_INTERVAL
    fi
done

echo "⚠️ Stack deletion still in progress after 30 minutes"
echo "Final status: $STACK_STATUS"
exit 1
