#!/bin/bash

RUN_ID="21055136164"
DEPLOYMENT_NUM="84"
LOG_FILE="deployment-84-monitor.log"

echo "=== Deployment #${DEPLOYMENT_NUM} Monitor ===" | tee -a "$LOG_FILE"
echo "Run ID: $RUN_ID" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

for i in {1..12}; do  # 12 checks = 60 minutes
    echo "[Check $i/12] $(date +%H:%M:%S)" | tee -a "$LOG_FILE"
    
    # Get workflow status
    STATUS=$(gh run view "$RUN_ID" --json status,conclusion --jq '.status + " " + (.conclusion // "none")')
    echo "GitHub Actions: $STATUS" | tee -a "$LOG_FILE"
    
    # Check if completed
    if echo "$STATUS" | grep -q "completed"; then
        CONCLUSION=$(echo "$STATUS" | awk '{print $2}')
        if [ "$CONCLUSION" = "success" ]; then
            echo "✅ Deployment completed successfully!" | tee -a "$LOG_FILE"
            exit 0
        else
            echo "❌ Deployment failed with conclusion: $CONCLUSION" | tee -a "$LOG_FILE"
            exit 1
        fi
    fi
    
    # Check CloudFormation stack
    STACK_STATUS=$(AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name CourtCaseManagementStack \
        --region us-east-1 \
        --query 'Stacks[0].StackStatus' \
        --output text 2>&1)
    
    if ! echo "$STACK_STATUS" | grep -q "does not exist"; then
        echo "CloudFormation: $STACK_STATUS" | tee -a "$LOG_FILE"
    fi
    
    echo "" | tee -a "$LOG_FILE"
    
    if [ $i -lt 12 ]; then
        sleep 300  # 5 minutes
    fi
done

echo "⚠️ Deployment still in progress after 60 minutes" | tee -a "$LOG_FILE"
