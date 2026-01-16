#!/bin/bash

# Monitor ECS Tasks for Deployment #90
CLUSTER_NAME="CourtCaseManagementStack-BackendCluster"
SERVICE_NAME="CourtCaseManagementStack-BackendService"
REGION="us-east-1"
LOG_FILE="ecs-tasks-91-monitor.log"

echo "=== ECS Task Monitoring Started ===" | tee -a "$LOG_FILE"
echo "Cluster: $CLUSTER_NAME" | tee -a "$LOG_FILE"
echo "Service: $SERVICE_NAME" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Monitor for up to 60 minutes (120 checks x 30 seconds)
for i in {1..120}; do
    # Check if cluster exists
    cluster_exists=$(AWS_PAGER="" aws ecs describe-clusters \
        --clusters "$CLUSTER_NAME" \
        --region "$REGION" \
        --query 'clusters[0].status' \
        --output text 2>/dev/null)
    
    if [ "$cluster_exists" = "ACTIVE" ]; then
        echo "=== Check $i at $(date) ===" | tee -a "$LOG_FILE"
        
        # Get service status
        AWS_PAGER="" aws ecs describe-services \
            --cluster "$CLUSTER_NAME" \
            --services "$SERVICE_NAME" \
            --region "$REGION" \
            --query 'services[0].[runningCount,desiredCount,deployments[0].rolloutState]' \
            --output text 2>&1 | tee -a "$LOG_FILE"
        
        # List tasks
        task_arns=$(AWS_PAGER="" aws ecs list-tasks \
            --cluster "$CLUSTER_NAME" \
            --service-name "$SERVICE_NAME" \
            --region "$REGION" \
            --query 'taskArns' \
            --output text 2>/dev/null)
        
        if [ -n "$task_arns" ]; then
            echo "Tasks found: $task_arns" | tee -a "$LOG_FILE"
            
            # Get task details
            AWS_PAGER="" aws ecs describe-tasks \
                --cluster "$CLUSTER_NAME" \
                --tasks $task_arns \
                --region "$REGION" \
                --query 'tasks[].[taskArn,lastStatus,healthStatus,stoppedReason]' \
                --output text 2>&1 | tee -a "$LOG_FILE"
            
            # Check for stopped tasks
            stopped_tasks=$(AWS_PAGER="" aws ecs describe-tasks \
                --cluster "$CLUSTER_NAME" \
                --tasks $task_arns \
                --region "$REGION" \
                --query 'tasks[?lastStatus==`STOPPED`].[taskArn,stoppedReason]' \
                --output text 2>/dev/null)
            
            if [ -n "$stopped_tasks" ]; then
                echo "⚠️ STOPPED TASKS DETECTED:" | tee -a "$LOG_FILE"
                echo "$stopped_tasks" | tee -a "$LOG_FILE"
            fi
        else
            echo "No tasks found yet" | tee -a "$LOG_FILE"
        fi
        
        echo "" | tee -a "$LOG_FILE"
    fi
    
    # Wait 30 seconds before next check
    sleep 30
done

echo "=== ECS Monitoring Ended at $(date) ===" | tee -a "$LOG_FILE"
