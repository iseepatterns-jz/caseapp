#!/bin/bash

DEPLOYMENT_NUM="84"
LOG_FILE="ecs-tasks-84-monitor.log"
REGION="us-east-1"

echo "=== ECS Task Monitor for Deployment #${DEPLOYMENT_NUM} ===" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Wait for cluster to be created
echo "Waiting for ECS cluster..." | tee -a "$LOG_FILE"
for i in {1..20}; do
    CLUSTER=$(AWS_PAGER="" aws ecs list-clusters --region "$REGION" --query 'clusterArns[0]' --output text 2>&1)
    
    if [ "$CLUSTER" != "None" ] && [ -n "$CLUSTER" ]; then
        CLUSTER_NAME=$(echo "$CLUSTER" | awk -F'/' '{print $NF}')
        echo "✅ Cluster found: $CLUSTER_NAME" | tee -a "$LOG_FILE"
        break
    fi
    
    sleep 30
done

if [ "$CLUSTER" = "None" ] || [ -z "$CLUSTER" ]; then
    echo "⚠️ No cluster found after 10 minutes" | tee -a "$LOG_FILE"
    exit 1
fi

# Monitor tasks
echo "" | tee -a "$LOG_FILE"
echo "Monitoring ECS tasks..." | tee -a "$LOG_FILE"

for i in {1..40}; do  # 20 minutes of task monitoring
    echo "[Task Check $i] $(date +%H:%M:%S)" | tee -a "$LOG_FILE"
    
    # List tasks
    TASKS=$(AWS_PAGER="" aws ecs list-tasks --cluster "$CLUSTER_NAME" --region "$REGION" --query 'taskArns' --output text 2>&1)
    
    if [ -n "$TASKS" ] && [ "$TASKS" != "None" ]; then
        TASK_COUNT=$(echo "$TASKS" | wc -w)
        echo "Tasks found: $TASK_COUNT" | tee -a "$LOG_FILE"
        
        # Check task status
        for TASK_ARN in $TASKS; do
            TASK_STATUS=$(AWS_PAGER="" aws ecs describe-tasks \
                --cluster "$CLUSTER_NAME" \
                --tasks "$TASK_ARN" \
                --region "$REGION" \
                --query 'tasks[0].[lastStatus,healthStatus,stopCode,stoppedReason]' \
                --output text 2>&1)
            
            echo "Task: $TASK_STATUS" | tee -a "$LOG_FILE"
            
            # Check for stopped tasks
            if echo "$TASK_STATUS" | grep -q "STOPPED"; then
                echo "⚠️ Task stopped - checking reason..." | tee -a "$LOG_FILE"
                STOP_REASON=$(echo "$TASK_STATUS" | awk '{print $4}')
                echo "Stop reason: $STOP_REASON" | tee -a "$LOG_FILE"
                
                # Get CloudWatch logs
                LOG_GROUP=$(AWS_PAGER="" aws logs describe-log-groups \
                    --region "$REGION" \
                    --query 'logGroups[?contains(logGroupName, `Backend`)].logGroupName' \
                    --output text 2>&1 | head -1)
                
                if [ -n "$LOG_GROUP" ]; then
                    echo "Fetching logs from: $LOG_GROUP" | tee -a "$LOG_FILE"
                    AWS_PAGER="" aws logs tail "$LOG_GROUP" --region "$REGION" --since 5m 2>&1 | tail -50 | tee -a "$LOG_FILE"
                fi
            fi
        done
    else
        echo "No tasks yet..." | tee -a "$LOG_FILE"
    fi
    
    echo "" | tee -a "$LOG_FILE"
    sleep 30
done

echo "Task monitoring completed" | tee -a "$LOG_FILE"
