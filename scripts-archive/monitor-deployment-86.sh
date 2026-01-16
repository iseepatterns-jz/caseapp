#!/bin/bash
# Monitor deployment #86 actively
# Run ID: 21057124658

set -euo pipefail

RUN_ID="21057124658"
STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"
LOG_FILE="deployment-86-monitor.log"

echo "=== Deployment #86 Monitoring Started ===" | tee -a "$LOG_FILE"
echo "Run ID: $RUN_ID" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Monitor for up to 60 minutes (120 checks at 30 second intervals)
for i in {1..120}; do
    echo "[Check $i/120] $(date)" | tee -a "$LOG_FILE"
    
    # Check GitHub Actions status
    status=$(gh run view "$RUN_ID" --json status,conclusion 2>/dev/null | jq -r '.status' || echo "unknown")
    conclusion=$(gh run view "$RUN_ID" --json status,conclusion 2>/dev/null | jq -r '.conclusion' || echo "")
    
    echo "  GitHub Actions: status=$status, conclusion=$conclusion" | tee -a "$LOG_FILE"
    
    # Check CloudFormation stack
    stack_status=$(AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    echo "  CloudFormation: $stack_status" | tee -a "$LOG_FILE"
    
    # Check for ECS cluster
    cluster=$(AWS_PAGER="" aws ecs list-clusters --region "$REGION" --query 'clusterArns' --output text 2>/dev/null | grep -i courtcase | head -1 || echo "")
    
    if [ -n "$cluster" ]; then
        cluster_name=$(echo "$cluster" | awk -F'/' '{print $NF}')
        echo "  ECS Cluster: $cluster_name" | tee -a "$LOG_FILE"
        
        # Check for services
        services=$(AWS_PAGER="" aws ecs list-services --cluster "$cluster_name" --region "$REGION" --query 'serviceArns' --output text 2>/dev/null || echo "")
        
        if [ -n "$services" ]; then
            echo "  ECS Services found: $(echo "$services" | wc -w)" | tee -a "$LOG_FILE"
            
            # Check task status for each service
            for service_arn in $services; do
                service_name=$(echo "$service_arn" | awk -F'/' '{print $NF}')
                
                # Get service details
                service_info=$(AWS_PAGER="" aws ecs describe-services \
                    --cluster "$cluster_name" \
                    --services "$service_name" \
                    --region "$REGION" 2>/dev/null || echo "")
                
                if [ -n "$service_info" ]; then
                    running=$(echo "$service_info" | jq -r '.services[0].runningCount' 2>/dev/null || echo "0")
                    desired=$(echo "$service_info" | jq -r '.services[0].desiredCount' 2>/dev/null || echo "0")
                    echo "    Service $service_name: running=$running, desired=$desired" | tee -a "$LOG_FILE"
                fi
            done
            
            # Check for stopped tasks
            stopped_tasks=$(AWS_PAGER="" aws ecs list-tasks \
                --cluster "$cluster_name" \
                --region "$REGION" \
                --desired-status STOPPED \
                --query 'taskArns' \
                --output text 2>/dev/null | wc -w)
            
            if [ "$stopped_tasks" -gt 0 ]; then
                echo "  ⚠️  WARNING: $stopped_tasks stopped tasks found" | tee -a "$LOG_FILE"
            fi
        fi
    else
        echo "  ECS Cluster: Not created yet" | tee -a "$LOG_FILE"
    fi
    
    # Check if deployment completed or failed
    if [ "$status" = "completed" ]; then
        echo "" | tee -a "$LOG_FILE"
        echo "=== Deployment Completed ===" | tee -a "$LOG_FILE"
        echo "Conclusion: $conclusion" | tee -a "$LOG_FILE"
        echo "Finished: $(date)" | tee -a "$LOG_FILE"
        
        if [ "$conclusion" = "success" ]; then
            echo "✅ DEPLOYMENT SUCCESSFUL!" | tee -a "$LOG_FILE"
            exit 0
        else
            echo "❌ DEPLOYMENT FAILED!" | tee -a "$LOG_FILE"
            exit 1
        fi
    fi
    
    echo "" | tee -a "$LOG_FILE"
    
    # Wait 30 seconds before next check
    sleep 30
done

echo "⏱️  Monitoring timeout reached (60 minutes)" | tee -a "$LOG_FILE"
exit 2
