#!/bin/bash
echo "Waiting for CloudFormation stack deletion to complete..."
echo "Started at: $(date)"

for i in {1..30}; do
    STATUS=$(AWS_PAGER="" aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --query 'Stacks[0].StackStatus' 2>/dev/null || echo "DELETED")
    
    if [ "$STATUS" = "DELETED" ]; then
        echo "✅ Stack deleted successfully at $(date)"
        exit 0
    fi
    
    echo "[Check $i/30] Stack status: $STATUS"
    sleep 20
done

echo "⚠️ Timeout waiting for stack deletion"
exit 1
