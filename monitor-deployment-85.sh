#!/bin/bash
RUN_ID=21056671328
STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"

echo "=== Deployment #85 Monitor ==="
echo "Run ID: $RUN_ID"
echo "Started: $(date)"
echo ""

for i in {1..12}; do
    echo "[Check $i/12] $(date +%H:%M:%S)"
    
    # Check GitHub Actions status
    gh_status=$(AWS_PAGER="" gh run view $RUN_ID --repo iseepatterns-jz/caseapp --json status,conclusion --jq '.status')
    echo "GitHub Actions: $gh_status"
    
    # Check CloudFormation stack if it exists
    stack_status=$(AWS_PAGER="" aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].StackStatus' 2>/dev/null | tr -d '"')
    if [ -n "$stack_status" ]; then
        echo "CloudFormation: $stack_status"
    fi
    
    echo ""
    
    # Check if completed
    if [ "$gh_status" = "completed" ]; then
        conclusion=$(AWS_PAGER="" gh run view $RUN_ID --repo iseepatterns-jz/caseapp --json conclusion --jq '.conclusion')
        echo "✅ Deployment completed with conclusion: $conclusion"
        break
    fi
    
    # Wait 5 minutes between checks
    sleep 300
done

if [ "$gh_status" != "completed" ]; then
    echo "⚠️ Deployment still in progress after 60 minutes"
fi
