#!/bin/bash

# Monitor Deployment #91 - Minimal Stack with PostgreSQL Fix
RUN_ID="21071576560"
STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"
LOG_FILE="deployment-91-monitor.log"

echo "=== Deployment #91 Monitoring Started ===" | tee -a "$LOG_FILE"
echo "Run ID: $RUN_ID" | tee -a "$LOG_FILE"
echo "Stack: $STACK_NAME" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Monitor for up to 60 minutes (12 checks x 5 minutes)
for i in {1..12}; do
    echo "=== Check $i at $(date) ===" | tee -a "$LOG_FILE"
    
    # Check GitHub Actions status
    echo "Checking GitHub Actions..." | tee -a "$LOG_FILE"
    gh run view "$RUN_ID" --json status,conclusion,createdAt,updatedAt 2>&1 | tee -a "$LOG_FILE"
    
    # Get workflow status
    status=$(gh run view "$RUN_ID" --json status --jq '.status' 2>/dev/null)
    conclusion=$(gh run view "$RUN_ID" --json conclusion --jq '.conclusion' 2>/dev/null)
    
    echo "Status: $status, Conclusion: $conclusion" | tee -a "$LOG_FILE"
    
    # Check CloudFormation stack
    echo "" | tee -a "$LOG_FILE"
    echo "Checking CloudFormation stack..." | tee -a "$LOG_FILE"
    AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].[StackStatus,StackStatusReason]' \
        --output text 2>&1 | tee -a "$LOG_FILE"
    
    # Check if deployment completed
    if [ "$status" = "completed" ]; then
        echo "" | tee -a "$LOG_FILE"
        echo "=== Deployment Completed ===" | tee -a "$LOG_FILE"
        echo "Conclusion: $conclusion" | tee -a "$LOG_FILE"
        
        if [ "$conclusion" = "success" ]; then
            echo "✅ DEPLOYMENT SUCCESSFUL!" | tee -a "$LOG_FILE"
        else
            echo "❌ DEPLOYMENT FAILED!" | tee -a "$LOG_FILE"
        fi
        
        break
    fi
    
    # Wait 5 minutes before next check
    if [ $i -lt 12 ]; then
        echo "" | tee -a "$LOG_FILE"
        echo "Waiting 5 minutes before next check..." | tee -a "$LOG_FILE"
        sleep 300
    fi
done

echo "" | tee -a "$LOG_FILE"
echo "=== Monitoring Ended at $(date) ===" | tee -a "$LOG_FILE"
