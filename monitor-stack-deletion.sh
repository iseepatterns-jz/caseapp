#!/bin/bash

export AWS_PAGER=""
STACK_NAME="CourtCaseManagementStack"

echo "=== Monitoring Stack Deletion ==="
echo "Time: $(date)"
echo ""

for i in {1..30}; do
    echo "=== Check #$i at $(date) ==="
    
    STATUS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].StackStatus' --output text 2>&1)
    
    if echo "$STATUS" | grep -q "does not exist"; then
        echo "✅ Stack deleted successfully!"
        exit 0
    elif echo "$STATUS" | grep -q "DELETE_COMPLETE"; then
        echo "✅ Stack deletion complete!"
        exit 0
    elif echo "$STATUS" | grep -q "DELETE_FAILED"; then
        echo "❌ Stack deletion failed!"
        aws cloudformation describe-stack-events --stack-name "$STACK_NAME" --max-items 5 --query 'StackEvents[?ResourceStatus==`DELETE_FAILED`]' --output json
        exit 1
    else
        echo "Status: $STATUS"
    fi
    
    echo ""
    sleep 30
done

echo "⏱️ Monitoring timeout after 15 minutes"
