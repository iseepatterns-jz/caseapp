#!/bin/bash
#
# Deployment Time Estimator
# Collects historical deployment data and estimates completion time
#
# Usage: bash deployment-time-estimator.sh <action> [args...]
# Actions: collect, estimate, update
#

set -euo pipefail

# Configuration
HISTORY_FILE=".deployment-registry/deployment-history.json"
STACK_NAME="${STACK_NAME:-CourtCaseManagementStack}"
REGION="${AWS_REGION:-us-east-1}"

# Ensure history file exists
init_history() {
    local dir=$(dirname "$HISTORY_FILE")
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
    fi
    
    if [ ! -f "$HISTORY_FILE" ]; then
        cat > "$HISTORY_FILE" <<EOF
{
  "deployments": [],
  "resource_averages": {
    "AWS::RDS::DBInstance": 900,
    "AWS::ECS::Service": 180,
    "AWS::ElasticLoadBalancingV2::LoadBalancer": 120,
    "AWS::EC2::VPC": 60,
    "AWS::EC2::SecurityGroup": 30,
    "AWS::IAM::Role": 30,
    "AWS::SecretsManager::Secret": 10
  },
  "average_deployment_minutes": 25,
  "last_updated": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    fi
}

# Collect historical deployment data from CloudFormation
collect_history() {
    local stack_name="${1:-$STACK_NAME}"
    
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Collecting deployment history for $stack_name..."
    
    init_history
    
    # Get stack events for completed deployments
    local stack_events=$(AWS_PAGER="" aws cloudformation describe-stack-events \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --max-items 100 \
        --query 'StackEvents[?ResourceStatus==`CREATE_COMPLETE` || ResourceStatus==`UPDATE_COMPLETE`]' \
        --output json 2>/dev/null || echo "[]")
    
    if [ "$stack_events" = "[]" ]; then
        echo "No deployment history found for $stack_name"
        return 0
    fi
    
    # Parse events to calculate deployment duration
    local create_start=$(echo "$stack_events" | jq -r '[.[] | select(.ResourceStatus=="CREATE_COMPLETE" and .ResourceType=="AWS::CloudFormation::Stack")] | .[0].Timestamp // empty')
    local create_end=$(echo "$stack_events" | jq -r '[.[] | select(.ResourceStatus=="CREATE_COMPLETE" and .ResourceType=="AWS::CloudFormation::Stack")] | .[-1].Timestamp // empty')
    
    if [ -n "$create_start" ] && [ -n "$create_end" ]; then
        local start_epoch=$(date -d "$create_start" "+%s" 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S%z" "$create_start" "+%s" 2>/dev/null || echo "0")
        local end_epoch=$(date -d "$create_end" "+%s" 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S%z" "$create_end" "+%s" 2>/dev/null || echo "0")
        
        if [ "$start_epoch" != "0" ] && [ "$end_epoch" != "0" ]; then
            local duration_minutes=$(( (end_epoch - start_epoch) / 60 ))
            
            echo "Found deployment: $create_start to $create_end ($duration_minutes minutes)"
            
            # Update history file
            local history=$(cat "$HISTORY_FILE")
            local new_deployment=$(cat <<EOF
{
  "stack_name": "$stack_name",
  "started_at": "$create_start",
  "completed_at": "$create_end",
  "duration_minutes": $duration_minutes,
  "collected_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
)
            
            local updated_history=$(echo "$history" | jq ".deployments += [$new_deployment]")
            echo "$updated_history" > "$HISTORY_FILE"
            
            # Recalculate average
            local avg=$(echo "$updated_history" | jq '[.deployments[].duration_minutes] | add / length')
            updated_history=$(echo "$updated_history" | jq ".average_deployment_minutes = $avg")
            echo "$updated_history" > "$HISTORY_FILE"
            
            echo "Updated average deployment time: $avg minutes"
        fi
    fi
    
    # Collect resource-specific timing
    local resource_types=$(echo "$stack_events" | jq -r '[.[].ResourceType] | unique | .[]')
    
    while IFS= read -r resource_type; do
        [ -z "$resource_type" ] && continue
        
        # Find first and last event for this resource type
        local first_event=$(echo "$stack_events" | jq -r "[.[] | select(.ResourceType==\"$resource_type\")] | .[0].Timestamp // empty")
        local last_event=$(echo "$stack_events" | jq -r "[.[] | select(.ResourceType==\"$resource_type\")] | .[-1].Timestamp // empty")
        
        if [ -n "$first_event" ] && [ -n "$last_event" ]; then
            local first_epoch=$(date -d "$first_event" "+%s" 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S%z" "$first_event" "+%s" 2>/dev/null || echo "0")
            local last_epoch=$(date -d "$last_event" "+%s" 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S%z" "$last_event" "+%s" 2>/dev/null || echo "0")
            
            if [ "$first_epoch" != "0" ] && [ "$last_epoch" != "0" ]; then
                local resource_duration=$(( (last_epoch - first_epoch) / 60 ))
                
                # Update resource average
                local history=$(cat "$HISTORY_FILE")
                local updated_history=$(echo "$history" | jq ".resource_averages[\"$resource_type\"] = $resource_duration")
                echo "$updated_history" > "$HISTORY_FILE"
            fi
        fi
    done <<< "$resource_types"
    
    echo "Deployment history collection complete"
}

# Estimate deployment completion time
estimate_completion() {
    local correlation_id="$1"
    local stack_name="${2:-$STACK_NAME}"
    local elapsed_minutes="${3:-0}"
    
    init_history
    
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Estimating completion time for $correlation_id..."
    
    # Read historical data
    local history=$(cat "$HISTORY_FILE")
    local avg_deployment=$(echo "$history" | jq -r '.average_deployment_minutes // 25')
    
    # Get current stack status
    local stack_status=$(AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "UNKNOWN")
    
    # Get resources being created
    local pending_resources=$(AWS_PAGER="" aws cloudformation describe-stack-resources \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query 'StackResources[?ResourceStatus==`CREATE_IN_PROGRESS`].ResourceType' \
        --output json 2>/dev/null || echo "[]")
    
    # Calculate estimated remaining time based on pending resources
    local estimated_remaining=0
    
    if [ "$pending_resources" != "[]" ]; then
        # Sum up estimated time for pending resources
        while IFS= read -r resource_type; do
            [ -z "$resource_type" ] && continue
            
            local resource_avg=$(echo "$history" | jq -r ".resource_averages[\"$resource_type\"] // 60")
            estimated_remaining=$((estimated_remaining + resource_avg / 60))
        done < <(echo "$pending_resources" | jq -r '.[]')
    else
        # No specific resources, use overall average
        estimated_remaining=$((avg_deployment - elapsed_minutes))
    fi
    
    # Ensure minimum estimate
    if [ $estimated_remaining -lt 5 ]; then
        estimated_remaining=5
    fi
    
    # Calculate confidence interval (±20%)
    local confidence_low=$((estimated_remaining * 80 / 100))
    local confidence_high=$((estimated_remaining * 120 / 100))
    
    # Return estimation
    cat <<EOF
{
  "correlation_id": "$correlation_id",
  "stack_name": "$stack_name",
  "stack_status": "$stack_status",
  "elapsed_minutes": $elapsed_minutes,
  "estimated_remaining_minutes": $estimated_remaining,
  "confidence_interval": {
    "low": $confidence_low,
    "high": $confidence_high
  },
  "estimated_total_minutes": $((avg_deployment)),
  "estimated_completion_time": "$(date -u -d "+${estimated_remaining} minutes" "+%Y-%m-%d %H:%M:%S UTC" 2>/dev/null || date -u -v+${estimated_remaining}M "+%Y-%m-%d %H:%M:%S UTC")"
}
EOF
}

# Update deployment history with completed deployment
update_history() {
    local correlation_id="$1"
    local duration_minutes="$2"
    local stack_name="${3:-$STACK_NAME}"
    
    init_history
    
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] Updating history with completed deployment: $correlation_id"
    
    local history=$(cat "$HISTORY_FILE")
    local new_deployment=$(cat <<EOF
{
  "correlation_id": "$correlation_id",
  "stack_name": "$stack_name",
  "duration_minutes": $duration_minutes,
  "completed_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
)
    
    # Add to history
    local updated_history=$(echo "$history" | jq ".deployments += [$new_deployment]")
    
    # Recalculate average (last 10 deployments)
    local avg=$(echo "$updated_history" | jq '[.deployments[-10:][].duration_minutes] | add / length')
    updated_history=$(echo "$updated_history" | jq ".average_deployment_minutes = $avg | .last_updated = \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"")
    
    echo "$updated_history" > "$HISTORY_FILE"
    
    echo "Updated average deployment time: $avg minutes (based on last 10 deployments)"
}

# Main script
ACTION="${1:-}"

case "$ACTION" in
    collect)
        shift
        collect_history "$@"
        ;;
    estimate)
        shift
        if [ $# -lt 1 ]; then
            echo "Usage: $0 estimate <correlation_id> [stack_name] [elapsed_minutes]"
            exit 1
        fi
        estimate_completion "$@"
        ;;
    update)
        shift
        if [ $# -lt 2 ]; then
            echo "Usage: $0 update <correlation_id> <duration_minutes> [stack_name]"
            exit 1
        fi
        update_history "$@"
        ;;
    *)
        echo "Usage: $0 <action> [args...]"
        echo "Actions:"
        echo "  collect [stack_name]                                    - Collect historical deployment data"
        echo "  estimate <correlation_id> [stack_name] [elapsed_mins]  - Estimate deployment completion time"
        echo "  update <correlation_id> <duration_mins> [stack_name]   - Update history with completed deployment"
        exit 1
        ;;
esac
