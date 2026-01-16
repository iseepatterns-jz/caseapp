#!/bin/bash
RUN_ID="21075198152"
STACK_NAME="CourtCaseManagementStack"
LOG_FILE="deployment-95-monitor.log"

echo "=== Deployment #95 Monitor ===" | tee -a $LOG_FILE
echo "Run ID: $RUN_ID" | tee -a $LOG_FILE
echo "Stack: $STACK_NAME" | tee -a $LOG_FILE
echo "Started: $(date)" | tee -a $LOG_FILE
echo "" | tee -a $LOG_FILE

while true; do
    TIMESTAMP=$(date '+%H:%M:%S')
    
    # Check GitHub Actions status
    GH_STATUS=$(gh run view $RUN_ID --repo iseepatterns-jz/caseapp --json status,conclusion 2>/dev/null | jq -r '.status + " | " + (.conclusion // "")')
    echo "[$TIMESTAMP] GitHub Actions: $GH_STATUS" | tee -a $LOG_FILE
    
    # Check CloudFormation stack
    STACK_STATUS=$(AWS_PAGER="" aws cloudformation describe-stacks --stack-name $STACK_NAME --region us-east-1 2>/dev/null | jq -r '.Stacks[0].StackStatus // "NOT_FOUND"')
    if [ "$STACK_STATUS" != "NOT_FOUND" ]; then
        echo "[$TIMESTAMP] CloudFormation: $STACK_STATUS" | tee -a $LOG_FILE
        
        # Check ECS cluster and services
        CLUSTER=$(AWS_PAGER="" aws ecs list-clusters --region us-east-1 2>/dev/null | jq -r '.clusterArns[] | select(contains("CourtCase"))' | head -1 | awk -F'/' '{print $NF}')
        if [ -n "$CLUSTER" ]; then
            echo "[$TIMESTAMP] ECS Cluster: $CLUSTER" | tee -a $LOG_FILE
            
            # List services
            SERVICES=$(AWS_PAGER="" aws ecs list-services --cluster $CLUSTER --region us-east-1 2>/dev/null | jq -r '.serviceArns[]' | awk -F'/' '{print $NF}')
            for SERVICE in $SERVICES; do
                COUNTS=$(AWS_PAGER="" aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region us-east-1 2>/dev/null | jq -r '.services[0] | "\(.runningCount)/\(.desiredCount) running"')
                echo "[$TIMESTAMP]   $SERVICE: $COUNTS" | tee -a $LOG_FILE
            done
        fi
    fi
    
    echo "" | tee -a $LOG_FILE
    
    # Check if workflow completed
    if [[ "$GH_STATUS" == "completed"* ]]; then
        echo "[$TIMESTAMP] ✅ Workflow completed!" | tee -a $LOG_FILE
        break
    fi
    
    # Check for timeout (60 minutes)
    if [ $(grep -c "GitHub Actions" $LOG_FILE) -gt 72 ]; then
        echo "[$TIMESTAMP] ⏱️  Timeout after 3600 seconds" | tee -a $LOG_FILE
        break
    fi
    
    sleep 300  # 5 minutes
done
