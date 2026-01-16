#!/bin/bash

# Wait for CloudFormation deletion to complete and verification to pass
# Checks every 2 minutes until safe to deploy

set -euo pipefail

export AWS_PAGER=""
stty -ixon -ixoff 2>/dev/null || true

STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"
CHECK_INTERVAL=120  # 2 minutes

echo "=== Waiting for Verification to Pass ==="
echo "Stack: $STACK_NAME"
echo "Started: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""
echo "Checking every 2 minutes..."
echo ""

ITERATION=1

while true; do
    echo "--- Check #$ITERATION at $(date -u '+%H:%M:%S UTC') ---"
    
    # Check if stack still exists
    STACK_STATUS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" 2>/dev/null | jq -r '.Stacks[0].StackStatus' || echo "DELETED")
    
    if [[ "$STACK_STATUS" == "DELETED" ]]; then
        echo "✅ CloudFormation stack deleted!"
        echo ""
        echo "Running verification script..."
        echo ""
        
        # Run verification
        if ./verify-resources-before-deploy.sh; then
            echo ""
            echo "🎉 ✅ VERIFICATION PASSED - SAFE TO DEPLOY! 🎉"
            echo ""
            echo "Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
            echo ""
            echo "Next steps:"
            echo "1. Deploy the fix:"
            echo "   git push origin main"
            echo ""
            echo "2. Monitor deployment:"
            echo "   gh run list --limit 1"
            echo "   gh run watch"
            echo ""
            exit 0
        else
            echo ""
            echo "⚠️  Verification failed, waiting for resources to clean up..."
            echo "Will check again in 2 minutes"
            echo ""
        fi
    else
        echo "CloudFormation: $STACK_STATUS"
        echo "Still waiting for deletion to complete..."
        echo ""
    fi
    
    ITERATION=$((ITERATION + 1))
    sleep "$CHECK_INTERVAL"
done
