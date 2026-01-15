#!/bin/bash

# Monitor deployment #20979184945 for natural failure
# Checks every 3 minutes until failure is detected

set -euo pipefail

# Disable pagers
export AWS_PAGER=""
stty -ixon -ixoff 2>/dev/null || true

RUN_ID="20979184945"
STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"
CHECK_INTERVAL=180  # 3 minutes

echo "=== Deployment Failure Monitor ==="
echo "Run ID: $RUN_ID"
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo "Check Interval: ${CHECK_INTERVAL}s (3 minutes)"
echo ""
echo "Monitoring started at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Press Ctrl+C to stop monitoring"
echo ""

ITERATION=1

while true; do
    echo "--- Check #$ITERATION at $(date -u '+%H:%M:%S UTC') ---"
    
    # Check GitHub Actions status
    GH_STATUS=$(gh run view "$RUN_ID" --json status,conclusion 2>/dev/null | jq -r '.status')
    GH_CONCLUSION=$(gh run view "$RUN_ID" --json status,conclusion 2>/dev/null | jq -r '.conclusion // "N/A"')
    
    echo "GitHub Actions: $GH_STATUS | Conclusion: $GH_CONCLUSION"
    
    # Check CloudFormation stack status
    CFN_STATUS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" 2>/dev/null | jq -r '.Stacks[0].StackStatus' || echo "STACK_NOT_FOUND")
    
    echo "CloudFormation: $CFN_STATUS"
    
    # Check if deployment has failed
    if [[ "$GH_STATUS" == "completed" ]]; then
        echo ""
        echo "🔴 GitHub Actions deployment completed!"
        echo "Conclusion: $GH_CONCLUSION"
        
        if [[ "$GH_CONCLUSION" == "failure" ]]; then
            echo "✅ Natural failure detected as expected"
        else
            echo "⚠️  Unexpected conclusion: $GH_CONCLUSION"
        fi
        
        echo ""
        echo "Final CloudFormation Status: $CFN_STATUS"
        break
    fi
    
    # Check if CloudFormation has failed
    if [[ "$CFN_STATUS" =~ ROLLBACK|FAILED|DELETE ]]; then
        echo ""
        echo "🔴 CloudFormation stack failure detected!"
        echo "Status: $CFN_STATUS"
        
        # Get failure reason
        REASON=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --region "$REGION" 2>/dev/null | jq -r '.Stacks[0].StackStatusReason // "N/A"')
        
        echo "Reason: $REASON"
        echo ""
        echo "✅ Natural failure detected - safe to proceed with new deployment"
        break
    fi
    
    # Check ECS service status
    ECS_CLUSTER=$(aws ecs list-clusters --region "$REGION" 2>/dev/null | \
        jq -r '.clusterArns[]' | grep -i court | head -1 || echo "")
    
    if [[ -n "$ECS_CLUSTER" ]]; then
        ECS_SERVICE=$(aws ecs list-services --cluster "$ECS_CLUSTER" --region "$REGION" 2>/dev/null | \
            jq -r '.serviceArns[]' | grep -i backend | head -1 || echo "")
        
        if [[ -n "$ECS_SERVICE" ]]; then
            RUNNING_COUNT=$(aws ecs describe-services \
                --cluster "$ECS_CLUSTER" \
                --services "$ECS_SERVICE" \
                --region "$REGION" 2>/dev/null | \
                jq -r '.services[0].runningCount' || echo "0")
            
            echo "ECS Tasks Running: $RUNNING_COUNT/2"
        fi
    fi
    
    echo ""
    echo "Still waiting... Next check in 3 minutes"
    echo ""
    
    ITERATION=$((ITERATION + 1))
    sleep "$CHECK_INTERVAL"
done

echo ""
echo "=== Monitoring Complete ==="
echo "Stopped at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""
echo "Next steps:"
echo "1. Verify resource cleanup with: ./verify-resources-before-deploy.sh"
echo "2. Deploy fix with: git push origin main"
