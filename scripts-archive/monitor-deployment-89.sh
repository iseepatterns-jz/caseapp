#!/bin/bash
set -euo pipefail

export AWS_PAGER=""
stty -ixon -ixoff 2>/dev/null || true

RUN_ID="21060189623"
STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"
MAX_WAIT=3600  # 60 minutes
CHECK_INTERVAL=300  # Check every 5 minutes

echo "=== Deployment #89 Monitor ==="
echo "Run ID: $RUN_ID"
echo "Stack: $STACK_NAME"
echo "Started: $(date)"
echo ""

elapsed=0
last_status=""

while [ $elapsed -lt $MAX_WAIT ]; do
    timestamp=$(date +%H:%M:%S)
    
    # Check GitHub Actions status
    gh_status=$(gh run view "$RUN_ID" --json status,conclusion 2>/dev/null | jq -r '.status' || echo "unknown")
    gh_conclusion=$(gh run view "$RUN_ID" --json status,conclusion 2>/dev/null | jq -r '.conclusion' || echo "null")
    
    echo "[$timestamp] GitHub Actions: $gh_status | Conclusion: $gh_conclusion"
    
    # Check CloudFormation stack if it exists
    stack_status=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" 2>/dev/null | jq -r '.Stacks[0].StackStatus' || echo "NOT_FOUND")
    
    if [ "$stack_status" != "NOT_FOUND" ]; then
        echo "[$timestamp] CloudFormation: $stack_status"
        
        # Check for ECS cluster
        cluster=$(aws ecs list-clusters --region "$REGION" 2>/dev/null | \
            jq -r '.clusterArns[] | select(contains("CourtCase"))' | head -1 || echo "")
        
        if [ -n "$cluster" ]; then
            cluster_name=$(echo "$cluster" | awk -F'/' '{print $NF}')
            echo "[$timestamp] ECS Cluster: $cluster_name"
            
            # Check services
            services=$(aws ecs list-services --cluster "$cluster_name" --region "$REGION" 2>/dev/null | \
                jq -r '.serviceArns[]' || echo "")
            
            if [ -n "$services" ]; then
                for service_arn in $services; do
                    service_name=$(echo "$service_arn" | awk -F'/' '{print $NF}')
                    service_info=$(aws ecs describe-services \
                        --cluster "$cluster_name" \
                        --services "$service_name" \
                        --region "$REGION" 2>/dev/null | \
                        jq -r '.services[0] | "\(.serviceName): \(.runningCount)/\(.desiredCount) running"')
                    echo "[$timestamp]   $service_info"
                done
            fi
        fi
    fi
    
    # Check if deployment completed
    if [ "$gh_status" = "completed" ]; then
        echo ""
        echo "[$timestamp] ✅ GitHub Actions workflow completed"
        echo "[$timestamp] Conclusion: $gh_conclusion"
        
        if [ "$gh_conclusion" = "success" ]; then
            echo "[$timestamp] 🎉 DEPLOYMENT SUCCESSFUL!"
            exit 0
        else
            echo "[$timestamp] ❌ DEPLOYMENT FAILED"
            exit 1
        fi
    fi
    
    echo ""
    sleep $CHECK_INTERVAL
    elapsed=$((elapsed + CHECK_INTERVAL))
done

echo "[$timestamp] ⏱️  Timeout after $MAX_WAIT seconds"
exit 1
