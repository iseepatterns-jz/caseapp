#!/bin/bash
REGION="us-east-1"

echo "=== ECS Tasks Monitor for Deployment #85 ==="
echo "Started: $(date)"
echo ""

# Wait for cluster to be created
echo "Waiting for ECS cluster..."
for i in {1..20}; do
    CLUSTER=$(AWS_PAGER="" aws ecs list-clusters --region $REGION --query 'clusterArns[0]' --output text 2>/dev/null)
    if [ "$CLUSTER" != "None" ] && [ -n "$CLUSTER" ]; then
        echo "✅ Cluster found: $CLUSTER"
        break
    fi
    sleep 30
done

if [ -z "$CLUSTER" ] || [ "$CLUSTER" = "None" ]; then
    echo "❌ No cluster found after 10 minutes"
    exit 1
fi

# Monitor tasks
for i in {1..60}; do
    echo ""
    echo "[Task Check $i] $(date +%H:%M:%S)"
    
    # List services
    SERVICES=$(AWS_PAGER="" aws ecs list-services --cluster "$CLUSTER" --region $REGION --query 'serviceArns' --output text 2>/dev/null)
    
    if [ -z "$SERVICES" ]; then
        echo "No services found yet"
        sleep 30
        continue
    fi
    
    # Check each service
    for SERVICE in $SERVICES; do
        SERVICE_NAME=$(basename "$SERVICE")
        
        # Get service details
        SERVICE_INFO=$(AWS_PAGER="" aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" --region $REGION --query 'services[0].{Desired:desiredCount,Running:runningCount,Pending:pendingCount,Events:events[0].message}' 2>/dev/null)
        
        echo "Service: $SERVICE_NAME"
        echo "$SERVICE_INFO" | jq -r 'to_entries | .[] | "  \(.key): \(.value)"'
        
        # Get task ARNs
        TASKS=$(AWS_PAGER="" aws ecs list-tasks --cluster "$CLUSTER" --service-name "$SERVICE" --region $REGION --query 'taskArns' --output text 2>/dev/null)
        
        if [ -n "$TASKS" ]; then
            for TASK in $TASKS; do
                TASK_STATUS=$(AWS_PAGER="" aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK" --region $REGION --query 'tasks[0].{Status:lastStatus,Health:healthStatus,StopReason:stoppedReason}' 2>/dev/null)
                echo "  Task: $(basename $TASK)"
                echo "$TASK_STATUS" | jq -r 'to_entries | .[] | "    \(.key): \(.value)"'
            done
        fi
    done
    
    sleep 30
done

echo ""
echo "Task monitoring completed"
