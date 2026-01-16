#!/bin/bash
set -euo pipefail

# Monitor ECS tasks immediately after deployment starts
# This script checks ECS task status every 30 seconds and shows stopped task reasons

CLUSTER_NAME="${1:-CourtCaseManagementStack-ECSCluster}"
SERVICE_NAME="${2:-BackendService}"
MAX_CHECKS="${3:-40}"  # 40 checks * 30 sec = 20 minutes max

echo "=== ECS Task Immediate Monitor ==="
echo "Cluster: $CLUSTER_NAME"
echo "Service: $SERVICE_NAME"
echo "Max checks: $MAX_CHECKS ($(($MAX_CHECKS * 30 / 60)) minutes)"
echo ""

for i in $(seq 1 $MAX_CHECKS); do
    echo "[Check $i/$MAX_CHECKS] $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    
    # Check if cluster exists
    if ! AWS_PAGER="" aws ecs describe-clusters --clusters "$CLUSTER_NAME" --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
        echo "  ⏳ Cluster not yet active or doesn't exist"
        sleep 30
        continue
    fi
    
    # Check if service exists
    if ! AWS_PAGER="" aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
        echo "  ⏳ Service not yet active or doesn't exist"
        sleep 30
        continue
    fi
    
    # Get service details
    SERVICE_INFO=$(AWS_PAGER="" aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" --query 'services[0].{Running:runningCount,Desired:desiredCount,Pending:pendingCount}' --output json 2>/dev/null)
    
    RUNNING=$(echo "$SERVICE_INFO" | jq -r '.Running // 0')
    DESIRED=$(echo "$SERVICE_INFO" | jq -r '.Desired // 0')
    PENDING=$(echo "$SERVICE_INFO" | jq -r '.Pending // 0')
    
    echo "  📊 Tasks: $RUNNING/$DESIRED running, $PENDING pending"
    
    # Check for stopped tasks with reasons
    STOPPED_TASKS=$(AWS_PAGER="" aws ecs list-tasks --cluster "$CLUSTER_NAME" --service-name "$SERVICE_NAME" --desired-status STOPPED --max-items 5 --query 'taskArns' --output text 2>/dev/null || echo "")
    
    if [ -n "$STOPPED_TASKS" ]; then
        echo "  ⚠️  Found stopped tasks - checking reasons..."
        for task_arn in $STOPPED_TASKS; do
            TASK_INFO=$(AWS_PAGER="" aws ecs describe-tasks --cluster "$CLUSTER_NAME" --tasks "$task_arn" --query 'tasks[0].{StoppedReason:stoppedReason,StopCode:stopCode,Containers:containers[0].{Reason:reason,ExitCode:exitCode}}' --output json 2>/dev/null)
            
            STOPPED_REASON=$(echo "$TASK_INFO" | jq -r '.StoppedReason // "Unknown"')
            STOP_CODE=$(echo "$TASK_INFO" | jq -r '.StopCode // "Unknown"')
            CONTAINER_REASON=$(echo "$TASK_INFO" | jq -r '.Containers.Reason // "Unknown"')
            EXIT_CODE=$(echo "$TASK_INFO" | jq -r '.Containers.ExitCode // "Unknown"')
            
            echo "    ❌ Task: $(basename $task_arn)"
            echo "       Stop Code: $STOP_CODE"
            echo "       Stopped Reason: $STOPPED_REASON"
            echo "       Container Reason: $CONTAINER_REASON"
            echo "       Exit Code: $EXIT_CODE"
            
            # Check for secret-related errors
            if echo "$STOPPED_REASON" | grep -qi "secret\|ResourceInitializationError"; then
                echo "       🚨 SECRET ERROR DETECTED!"
                echo "       This is the RDS secret configuration issue"
            fi
        done
    fi
    
    # Check if we have healthy tasks
    if [ "$RUNNING" -ge "$DESIRED" ] && [ "$DESIRED" -gt 0 ]; then
        echo "  ✅ Service is healthy! $RUNNING/$DESIRED tasks running"
        
        # Get task ARNs and check CloudWatch logs
        TASK_ARNS=$(AWS_PAGER="" aws ecs list-tasks --cluster "$CLUSTER_NAME" --service-name "$SERVICE_NAME" --desired-status RUNNING --query 'taskArns[0]' --output text 2>/dev/null || echo "")
        
        if [ -n "$TASK_ARNS" ]; then
            echo "  📝 Checking CloudWatch logs for running task..."
            TASK_ID=$(basename "$TASK_ARNS")
            LOG_GROUP="/ecs/$SERVICE_NAME"
            
            # Try to get recent logs
            RECENT_LOGS=$(AWS_PAGER="" aws logs tail "$LOG_GROUP" --since 5m --format short 2>/dev/null | head -20 || echo "No logs yet")
            
            if [ "$RECENT_LOGS" != "No logs yet" ]; then
                echo "  Recent logs:"
                echo "$RECENT_LOGS" | sed 's/^/    /'
            fi
        fi
        
        exit 0
    fi
    
    sleep 30
done

echo ""
echo "❌ Timeout after $MAX_CHECKS checks"
echo "Service did not become healthy within $(($MAX_CHECKS * 30 / 60)) minutes"
exit 1
