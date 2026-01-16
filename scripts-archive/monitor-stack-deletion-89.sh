#!/bin/bash
set -euo pipefail

export AWS_PAGER=""
stty -ixon -ixoff 2>/dev/null || true

STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"
MAX_WAIT=1800  # 30 minutes
INTERVAL=30    # Check every 30 seconds

echo "=== Stack Deletion Monitor for Deployment #89 ==="
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo "Started: $(date)"
echo ""

elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    # Check stack status
    status=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" 2>/dev/null | jq -r '.Stacks[0].StackStatus' || echo "DELETED")
    
    if [ "$status" = "DELETED" ] || [ "$status" = "DELETE_COMPLETE" ]; then
        echo "[$(date +%H:%M:%S)] ✅ Stack deletion COMPLETE"
        echo ""
        echo "=== Verifying Clean Environment ==="
        
        # Check for any remaining resources
        vpcs=$(aws ec2 describe-vpcs \
            --filters "Name=tag:aws:cloudformation:stack-name,Values=$STACK_NAME" \
            --region "$REGION" 2>/dev/null | jq -r '.Vpcs | length')
        
        echo "Remaining VPCs: $vpcs"
        
        if [ "$vpcs" -eq 0 ]; then
            echo "✅ Environment is clean - ready for deployment #89"
        else
            echo "⚠️  VPCs still exist - waiting for cleanup..."
        fi
        
        exit 0
    fi
    
    # Count remaining resources
    resources=$(aws cloudformation describe-stack-resources \
        --stack-name "$STACK_NAME" \
        --region "$REGION" 2>/dev/null | \
        jq -r '[.StackResources[] | select(.ResourceStatus | contains("DELETE"))] | length' || echo "0")
    
    # Get resources still in progress
    in_progress=$(aws cloudformation describe-stack-resources \
        --stack-name "$STACK_NAME" \
        --region "$REGION" 2>/dev/null | \
        jq -r '.StackResources[] | select(.ResourceStatus == "DELETE_IN_PROGRESS") | .LogicalResourceId' | head -3)
    
    echo "[$(date +%H:%M:%S)] Status: $status | Resources: $resources"
    if [ -n "$in_progress" ]; then
        echo "  Deleting: $(echo "$in_progress" | tr '\n' ', ' | sed 's/,$//')"
    fi
    
    sleep $INTERVAL
    elapsed=$((elapsed + INTERVAL))
done

echo ""
echo "❌ Timeout after $MAX_WAIT seconds"
echo "Stack status: $status"
exit 1
