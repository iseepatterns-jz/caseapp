#!/bin/bash
#
# Registry Fallback Script
# Provides fallback coordination when deployment registry is unavailable
#
# Usage: bash registry-fallback.sh <action> [args...]
# Actions: can_deploy, get_active
#

set -euo pipefail

# Configuration
STACK_NAME="${STACK_NAME:-CourtCaseManagementStack}"
REGION="${AWS_REGION:-us-east-1}"

# Function to check if deployment can proceed using CloudFormation only
can_deploy_fallback() {
    local environment="${1:-production}"
    
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] [FALLBACK] Checking deployment status via CloudFormation only" >&2
    
    # Check CloudFormation stack status
    local stack_status=$(AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "DOES_NOT_EXIST")
    
    # Check if stack is in an active deployment state
    case "$stack_status" in
        CREATE_IN_PROGRESS|UPDATE_IN_PROGRESS|DELETE_IN_PROGRESS|ROLLBACK_IN_PROGRESS|UPDATE_ROLLBACK_IN_PROGRESS)
            # Active deployment detected
            local stack_events=$(AWS_PAGER="" aws cloudformation describe-stack-events \
                --stack-name "$STACK_NAME" \
                --region "$REGION" \
                --max-items 1 \
                --query 'StackEvents[0].Timestamp' \
                --output text 2>/dev/null || echo "UNKNOWN")
            
            # Calculate elapsed time (approximate)
            local current_time=$(date +%s)
            local event_time=$(date -d "$stack_events" +%s 2>/dev/null || echo "$current_time")
            local elapsed_seconds=$((current_time - event_time))
            local elapsed_minutes=$((elapsed_seconds / 60))
            
            # Estimate remaining time (rough estimate: 30 minutes total)
            local estimated_remaining=$((30 - elapsed_minutes))
            if [ $estimated_remaining -lt 0 ]; then
                estimated_remaining=5
            fi
            
            # Return active deployment info
            cat <<EOF
{
  "can_deploy": false,
  "reason": "active_deployment",
  "active_deployment": {
    "correlation_id": "unknown-fallback",
    "environment": "$environment",
    "status": "$stack_status",
    "started_at": "$stack_events",
    "elapsed_minutes": $elapsed_minutes,
    "estimated_remaining_minutes": $estimated_remaining,
    "source": "cloudformation_fallback"
  }
}
EOF
            return 1
            ;;
        DOES_NOT_EXIST|CREATE_COMPLETE|UPDATE_COMPLETE|DELETE_COMPLETE)
            # No active deployment, can proceed
            cat <<EOF
{
  "can_deploy": true,
  "reason": "no_active_deployment",
  "stack_status": "$stack_status",
  "source": "cloudformation_fallback"
}
EOF
            return 0
            ;;
        *)
            # Failed or unknown state - allow deployment to proceed
            # (deployment will handle the error)
            cat <<EOF
{
  "can_deploy": true,
  "reason": "stack_in_failed_state",
  "stack_status": "$stack_status",
  "source": "cloudformation_fallback",
  "warning": "Stack is in state: $stack_status. Deployment may need cleanup first."
}
EOF
            return 0
            ;;
    esac
}

# Function to get active deployment info using CloudFormation only
get_active_fallback() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] [FALLBACK] Getting active deployment via CloudFormation only" >&2
    
    # Check CloudFormation stack status
    local stack_status=$(AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "DOES_NOT_EXIST")
    
    case "$stack_status" in
        CREATE_IN_PROGRESS|UPDATE_IN_PROGRESS|DELETE_IN_PROGRESS|ROLLBACK_IN_PROGRESS|UPDATE_ROLLBACK_IN_PROGRESS)
            # Get stack events
            local stack_events=$(AWS_PAGER="" aws cloudformation describe-stack-events \
                --stack-name "$STACK_NAME" \
                --region "$REGION" \
                --max-items 1 \
                --query 'StackEvents[0].Timestamp' \
                --output text 2>/dev/null || echo "UNKNOWN")
            
            # Calculate elapsed time
            local current_time=$(date +%s)
            local event_time=$(date -d "$stack_events" +%s 2>/dev/null || echo "$current_time")
            local elapsed_seconds=$((current_time - event_time))
            local elapsed_minutes=$((elapsed_seconds / 60))
            
            cat <<EOF
{
  "correlation_id": "unknown-fallback",
  "environment": "unknown",
  "status": "$stack_status",
  "started_at": "$stack_events",
  "elapsed_minutes": $elapsed_minutes,
  "source": "cloudformation_fallback"
}
EOF
            ;;
        *)
            echo "{}"
            ;;
    esac
}

# Main script
ACTION="${1:-}"

case "$ACTION" in
    can_deploy)
        shift
        can_deploy_fallback "$@"
        ;;
    get_active)
        get_active_fallback
        ;;
    *)
        echo "Usage: $0 <action> [args...]"
        echo "Actions:"
        echo "  can_deploy [environment]  - Check if deployment can proceed (CloudFormation only)"
        echo "  get_active                - Get active deployment info (CloudFormation only)"
        exit 1
        ;;
esac
