#!/bin/bash

# Slack Notifier Script
# Sends deployment notifications to Slack channels

set -euo pipefail

# Configuration
# Channel IDs (use IDs instead of names for reliability)
CHANNEL_KIRO_UPDATES="C0A9M9DPFUY"  # #kiro-updates
CHANNEL_KIRO_INTERACT="C0A95T7UU4R"  # #kiro-interact
DEFAULT_CHANNEL="$CHANNEL_KIRO_UPDATES"
REGION="${AWS_REGION:-us-east-1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Send message to Slack using MCP with retry queue integration
send_slack_message() {
    local channel="$1"
    local message="$2"
    local max_retries="${3:-3}"
    local notification_type="${4:-custom}"
    local notification_args="${5:-}"
    
    log_info "Sending message to $channel"
    
    # Try to send with retries
    local attempt=1
    while [ $attempt -le $max_retries ]; do
        if mcp_slack_conversations_add_message \
            --channel_id="$channel" \
            --payload="$message" 2>/dev/null; then
            log_info "Message sent successfully"
            return 0
        else
            log_error "Failed to send message (attempt $attempt/$max_retries)"
            if [ $attempt -lt $max_retries ]; then
                sleep $((attempt * 2))  # Exponential backoff
            fi
            attempt=$((attempt + 1))
        fi
    done
    
    log_error "Failed to send message after $max_retries attempts"
    
    # Queue for retry if we have notification details
    if [ -n "$notification_args" ]; then
        log_info "Queueing notification for retry: $notification_type"
        bash "$(dirname "$0")/slack-retry-queue.sh" queue "$notification_type" $notification_args 2>/dev/null || true
    fi
    
    return 1
}

# Notify deployment start
notify_deployment_start() {
    local correlation_id="$1"
    local environment="$2"
    local workflow_run_id="$3"
    local channel="${4:-$DEFAULT_CHANNEL}"
    
    local workflow_url="https://github.com/${GITHUB_REPOSITORY:-unknown}/actions/runs/${workflow_run_id}"
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    
    local message=$(cat <<EOF
🚀 **Deployment Started**

**Environment:** $environment
**Correlation ID:** \`$correlation_id\`
**Started:** $timestamp
**Workflow:** $workflow_url

Monitoring deployment progress...
EOF
)
    
    send_slack_message "$channel" "$message" 3 "start" "$correlation_id $environment $workflow_run_id $channel"
}

# Notify concurrent deployment detected
notify_concurrent_deployment() {
    local correlation_id="$1"
    local environment="$2"
    local active_deployment="$3"
    local channel="${4:-$DEFAULT_CHANNEL}"
    
    # Parse active deployment JSON
    local active_status=$(echo "$active_deployment" | jq -r '.status // "UNKNOWN"')
    local active_started=$(echo "$active_deployment" | jq -r '.started_at // "UNKNOWN"')
    local elapsed_minutes=$(echo "$active_deployment" | jq -r '.elapsed_minutes // 0')
    local estimated_remaining=$(echo "$active_deployment" | jq -r '.estimated_remaining_minutes // 0')
    
    # Get more accurate estimate if available
    local active_correlation=$(echo "$active_deployment" | jq -r '.correlation_id // "unknown"')
    if [ "$active_correlation" != "unknown" ]; then
        local estimate=$(bash "$(dirname "$0")/deployment-time-estimator.sh" estimate "$active_correlation" "" "$elapsed_minutes" 2>/dev/null || echo "{}")
        if [ "$estimate" != "{}" ]; then
            estimated_remaining=$(echo "$estimate" | jq -r '.estimated_remaining_minutes // 0')
            local completion_time=$(echo "$estimate" | jq -r '.estimated_completion_time // "unknown"')
            
            if [ "$completion_time" != "unknown" ]; then
                active_started="$active_started (Est. completion: $completion_time)"
            fi
        fi
    fi
    
    local message=$(cat <<EOF
⏸️ **Deployment Queued**

**Environment:** $environment
**Correlation ID:** \`$correlation_id\`

**Active Deployment Detected:**
- Status: $active_status
- Started: $active_started
- Elapsed: ${elapsed_minutes} minutes
- Estimated Remaining: ${estimated_remaining} minutes

This deployment will wait for the active deployment to complete.
EOF
)
    
    send_slack_message "$channel" "$message" 3 "concurrent" "$correlation_id $environment '$active_deployment' $channel"
}

# Notify deployment progress
notify_deployment_progress() {
    local correlation_id="$1"
    local stack_status="$2"
    local progress_details="$3"
    local channel="${4:-$DEFAULT_CHANNEL}"
    
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    
    # Get time estimate
    local estimate=$(bash "$(dirname "$0")/deployment-time-estimator.sh" estimate "$correlation_id" 2>/dev/null || echo "{}")
    local estimated_remaining="unknown"
    local completion_time=""
    
    if [ "$estimate" != "{}" ]; then
        estimated_remaining=$(echo "$estimate" | jq -r '.estimated_remaining_minutes // "unknown"')
        completion_time=$(echo "$estimate" | jq -r '.estimated_completion_time // ""')
    fi
    
    local message=$(cat <<EOF
⏳ **Deployment Progress Update**

**Correlation ID:** \`$correlation_id\`
**Status:** $stack_status
**Time:** $timestamp
EOF
)
    
    if [ "$estimated_remaining" != "unknown" ]; then
        message="$message
**Estimated Remaining:** ${estimated_remaining} minutes"
        if [ -n "$completion_time" ]; then
            message="$message
**Est. Completion:** $completion_time"
        fi
    fi
    
    message="$message

$progress_details"
    
    send_slack_message "$channel" "$message" 3 "progress" "$correlation_id '$stack_status' '$progress_details' $channel"
}

# Notify deployment complete
notify_deployment_complete() {
    local correlation_id="$1"
    local environment="$2"
    local duration_minutes="$3"
    local application_url="${4:-}"
    local channel="${5:-$DEFAULT_CHANNEL}"
    
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    
    local message=$(cat <<EOF
✅ **Deployment Successful**

**Environment:** $environment
**Correlation ID:** \`$correlation_id\`
**Completed:** $timestamp
**Duration:** ${duration_minutes} minutes
EOF
)
    
    if [ -n "$application_url" ]; then
        message="$message

**Application URL:** $application_url"
    fi
    
    message="$message

All services are healthy and running! 🎉"
    
    send_slack_message "$channel" "$message" 3 "complete" "$correlation_id $environment $duration_minutes '$application_url' $channel"
}

# Notify deployment failed
notify_deployment_failed() {
    local correlation_id="$1"
    local environment="$2"
    local error_details="$3"
    local stack_name="${4:-CourtCaseManagementStack}"
    local channel="${5:-$DEFAULT_CHANNEL}"
    
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    local console_url="https://console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks/stackinfo?stackId=${stack_name}"
    
    local message=$(cat <<EOF
❌ **Deployment Failed**

**Environment:** $environment
**Correlation ID:** \`$correlation_id\`
**Failed:** $timestamp

**Error Details:**
$error_details

**Troubleshooting:**
- View stack events: $console_url
- Check CloudWatch logs for detailed error messages
- Review recent code changes

Need help? Check the deployment troubleshooting guide.
EOF
)
    
    send_slack_message "$channel" "$message" 3 "failed" "$correlation_id $environment '$error_details' $stack_name $channel"
}

# Notify deployment stalled
notify_deployment_stalled() {
    local correlation_id="$1"
    local stack_name="$2"
    local stall_duration_minutes="$3"
    local channel="${4:-$DEFAULT_CHANNEL}"
    
    local console_url="https://console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks/stackinfo?stackId=${stack_name}"
    
    local message=$(cat <<EOF
⚠️ **Deployment Stalled**

**Correlation ID:** \`$correlation_id\`
**Stack:** $stack_name
**No events for:** ${stall_duration_minutes} minutes

The deployment appears to be stalled. This could indicate:
- Long-running resource creation (RDS, etc.)
- Network connectivity issues
- AWS service delays

**Monitor:** $console_url

Continuing to monitor...
EOF
)
    
    send_slack_message "$channel" "$message" 3 "stalled" "$correlation_id $stack_name $stall_duration_minutes $channel"
}

# Show usage
usage() {
    cat <<EOF
Usage: $0 <command> [arguments]

Commands:
  start <correlation_id> <environment> <workflow_run_id> [channel]
      Notify deployment start
      
  concurrent <correlation_id> <environment> <active_deployment_json> [channel]
      Notify concurrent deployment detected
      
  progress <correlation_id> <stack_status> <progress_details> [channel]
      Notify deployment progress
      
  complete <correlation_id> <environment> <duration_minutes> [application_url] [channel]
      Notify deployment completion
      
  failed <correlation_id> <environment> <error_details> [stack_name] [channel]
      Notify deployment failure
      
  stalled <correlation_id> <stack_name> <stall_duration_minutes> [channel]
      Notify deployment stalled

Examples:
  $0 start 20260114-123456-abc123 production 12345
  $0 concurrent 20260114-123456-abc123 production '{"status":"CREATE_IN_PROGRESS"}'
  $0 progress 20260114-123456-abc123 UPDATE_IN_PROGRESS "Creating ECS cluster..."
  $0 complete 20260114-123456-abc123 production 25 https://app.example.com
  $0 failed 20260114-123456-abc123 production "RDS creation failed"
  $0 stalled 20260114-123456-abc123 CourtCaseManagementStack 15
EOF
}

# Main command dispatcher
main() {
    if [ $# -lt 1 ]; then
        usage
        exit 1
    fi
    
    local command="$1"
    shift
    
    case "$command" in
        start)
            if [ $# -lt 3 ]; then
                log_error "Missing required arguments"
                usage
                exit 1
            fi
            notify_deployment_start "$@"
            ;;
        concurrent)
            if [ $# -lt 3 ]; then
                log_error "Missing required arguments"
                usage
                exit 1
            fi
            notify_concurrent_deployment "$@"
            ;;
        progress)
            if [ $# -lt 3 ]; then
                log_error "Missing required arguments"
                usage
                exit 1
            fi
            notify_deployment_progress "$@"
            ;;
        complete)
            if [ $# -lt 3 ]; then
                log_error "Missing required arguments"
                usage
                exit 1
            fi
            notify_deployment_complete "$@"
            ;;
        failed)
            if [ $# -lt 3 ]; then
                log_error "Missing required arguments"
                usage
                exit 1
            fi
            notify_deployment_failed "$@"
            ;;
        stalled)
            if [ $# -lt 3 ]; then
                log_error "Missing required arguments"
                usage
                exit 1
            fi
            notify_deployment_stalled "$@"
            ;;
        *)
            log_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"
