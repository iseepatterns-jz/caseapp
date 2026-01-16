#!/bin/bash
set -euo pipefail

export AWS_PAGER=""
stty -ixon -ixoff 2>/dev/null || true

REGION="us-east-1"
MAX_WAIT=3600
CHECK_INTERVAL=30

echo "=== ECS Task Monitor for Deployment #89 ==="
echo "Started: $(date)"
echo ""

elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    timestamp=$(date +%H:%M:%S)
    
    # Find cluster
    cluster=$(aws ecs list-clusters --region "$REGION" 2>/dev/null | \
        jq -r '.clusterArns[] | select(contains("CourtCase"))' | head -1 || echo "")
    
    if [ -z "$cluster" ]; then
        echo "[$timestamp] Waiting for ECS cluster..."
        sleep $CHECK_INTERVAL
        elapsed=$((elapsed + CHECK_INTERVAL))
        continue
    fi
    
    cluster_name=$(echo "$cluster" | awk -F'/' '{print $NF}')
    echo "[$timestamp] Cluster: $cluster_name"
    
    # List all tasks
    tasks=$(aws ecs list-tasks --cluster "$cluster_name" --region "$REGION" 2>/dev/null | \
        jq -r '.taskArns[]' || echo "")
    
    if [ -n "$tasks" ]; then
        for task_arn in $tasks; do
            task_id=$(echo "$task_arn" | awk -F'/' '{print $NF}')
            task_info=$(aws ecs describe-tasks \
                --cluster "$cluster_name" \
                --tasks "$task_arn" \
                --region "$REGION" 2>/dev/null | \
                jq -r '.tasks[0] | "\(.lastStatus) | \(.healthStatus // "N/A")"')
            echo "[$timestamp]   Task ${task_id:0:8}: $task_info"
        done
    fi
    
    # Check for stopped tasks
    stopped_tasks=$(aws ecs list-tasks \
        --cluster "$cluster_name" \
        --desired-status STOPPED \
        --region "$REGION" 2>/dev/null | jq -r '.taskArns[]' | head -5 || echo "")
    
    if [ -n "$stopped_tasks" ]; then
        echo "[$timestamp] Recent stopped tasks:"
        for task_arn in $stopped_tasks; do
            task_id=$(echo "$task_arn" | awk -F'/' '{print $NF}')
            reason=$(aws ecs describe-tasks \
                --cluster "$cluster_name" \
                --tasks "$task_arn" \
                --region "$REGION" 2>/dev/null | \
                jq -r '.tasks[0].stoppedReason // "Unknown"')
            echo "[$timestamp]     ${task_id:0:8}: $reason"
        done
    fi
    
    echo ""
    sleep $CHECK_INTERVAL
    elapsed=$((elapsed + CHECK_INTERVAL))
done

echo "[$timestamp] Monitor timeout"
