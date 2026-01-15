#!/bin/bash

# Deployment Monitor Script
# Monitors CloudFormation stack deployment progress and sends notifications

set -euo pipefail

# Configuration
REGION="${AWS_REGION:-us-east-1}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"  # Check every 30 seconds
STALL_THRESHOLD="${STALL_THRESHOLD:-600}"  # Alert if no events for 10 minutes
MAX_DURATION="${MAX_DURATION:-2400}"  # Alert if deployment exceeds 40 minutes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo -e "${BLUE}[INFO]${NC} [$timestamp] $1"
}

log_success() {
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo -e "${GREEN}[SUCCESS]${NC} [$timestamp] $1"
}

log_warning() {
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo -e "${YELLOW}[WARNING]${NC} [$timestamp] $1"
}

log_error() {
    local timestamp=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo -e "${RED}[ERROR]${NC} [$timestamp] $1"
}

# Structured logging with correlation ID
log_structured() {
    local level="$1"
    local message="$2"
    local correlation_id="${3:-UNKNOWN}"
    local timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    
    # JSON log entry
    local log_entry=$(cat <<EOF
{
  "timestamp": "$timestamp",
  "level": "$level",
  "correlation_id": "$correlation_id",
  "message": "$message",
  "stack_name": "${STACK_NAME:-UNKNOWN}",
  "environment": "${ENVIRONMENT:-UNKNOWN}"
}
EOF
)
    
    # Write to log file if specified
    if [ -n "${LOG_FILE:-}" ]; then
        echo "$log_entry" >> "$LOG_FILE"
    fi
    
    # Also write to stdout
    echo "$log_entry"
}

# Get latest stack events
get_latest_events() {
    local stack_name="$1"
    local since_timestamp="${2:-}"
    
    local query='StackEvents[*].[Timestamp,LogicalResourceId,ResourceType,ResourceStatus,ResourceStatusReason]'
    
    AWS_PAGER="" aws cloudformation describe-stack-events \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query "$query" \
        --output json 2>/dev/null || echo "[]"
}

# Get stack status
get_stack_status() {
    local stack_name="$1"
    
    AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "STACK_NOT_FOUND"
}

# Check if stack status is terminal
is_terminal_status() {
    local status="$1"
    
    case "$status" in
        CREATE_COMPLETE|UPDATE_COMPLETE|DELETE_COMPLETE)
            return 0  # Success terminal states
            ;;
        CREATE_FAILED|UPDATE_FAILED|DELETE_FAILED|ROLLBACK_COMPLETE|ROLLBACK_FAILED|UPDATE_ROLLBACK_COMPLETE|UPDATE_ROLLBACK_FAILED)
            return 0  # Failure terminal states
            ;;
        *)
            return 1  # Non-terminal state
            ;;
    esac
}

# Check if stack status indicates failure
is_failure_status() {
    local status="$1"
    
    case "$status" in
        CREATE_FAILED|UPDATE_FAILED|DELETE_FAILED|ROLLBACK_COMPLETE|ROLLBACK_FAILED|UPDATE_ROLLBACK_COMPLETE|UPDATE_ROLLBACK_FAILED)
            return 0  # Failure state
            ;;
        *)
            return 1  # Not a failure state
            ;;
    esac
}

# Monitor deployment
monitor_deployment() {
    local correlation_id="$1"
    local stack_name="$2"
    local slack_channel="${3:-#kiro-updates}"
    local log_file="${4:-}"
    
    export STACK_NAME="$stack_name"
    export LOG_FILE="$log_file"
    export CORRELATION_ID="$correlation_id"
    
    log_info "Starting deployment monitoring"
    log_info "Correlation ID: $correlation_id"
    log_info "Stack: $stack_name"
    log_info "Slack Channel: $slack_channel"
    
    log_structured "INFO" "Monitoring started" "$correlation_id"
    
    local start_time=$(date "+%s")
    local last_event_time=$start_time
    local last_event_timestamp=""
    local check_count=0
    
    while true; do
        check_count=$((check_count + 1))
        local current_time=$(date "+%s")
        local elapsed=$((current_time - start_time))
        local since_last_event=$((current_time - last_event_time))
        
        # Get current stack status
        local stack_status=$(get_stack_status "$stack_name")
        
        if [ "$stack_status" = "STACK_NOT_FOUND" ]; then
            log_error "Stack not found: $stack_name"
            log_structured "ERROR" "Stack not found" "$correlation_id"
            return 1
        fi
        
        log_info "Check #$check_count: Status=$stack_status, Elapsed=${elapsed}s"
        
        # Get latest events
        local events=$(get_latest_events "$stack_name" "$last_event_timestamp")
        local event_count=$(echo "$events" | jq 'length')
        
        # Process new events
        if [ "$event_count" -gt 0 ]; then
            # Get the most recent event timestamp
            local latest_timestamp=$(echo "$events" | jq -r '.[0][0]')
            
            # Check if we have new events
            if [ "$latest_timestamp" != "$last_event_timestamp" ]; then
                log_info "Found $event_count new event(s)"
                
                # Log each new event
                echo "$events" | jq -r '.[] | @tsv' | while IFS=$'\t' read -r timestamp resource_id resource_type status reason; do
                    log_info "Event: $resource_type ($resource_id) -> $status"
                    if [ -n "$reason" ] && [ "$reason" != "null" ]; then
                        log_info "  Reason: $reason"
                    fi
                    
                    log_structured "EVENT" "$resource_type ($resource_id) -> $status" "$correlation_id"
                done
                
                last_event_timestamp="$latest_timestamp"
                last_event_time=$current_time
            fi
        fi
        
        # Check for stalls (no events for STALL_THRESHOLD seconds)
        if [ $since_last_event -gt $STALL_THRESHOLD ]; then
            local stall_minutes=$((since_last_event / 60))
            log_warning "Deployment stalled: No events for ${stall_minutes} minutes"
            log_structured "WARNING" "Deployment stalled: No events for ${stall_minutes} minutes" "$correlation_id"
            
            # Reset last event time to avoid repeated warnings
            last_event_time=$current_time
        fi
        
        # Check for excessive duration
        if [ $elapsed -gt $MAX_DURATION ]; then
            local duration_minutes=$((elapsed / 60))
            log_warning "Deployment duration exceeded: ${duration_minutes} minutes"
            log_structured "WARNING" "Deployment duration exceeded: ${duration_minutes} minutes" "$correlation_id"
        fi
        
        # Check if deployment is complete
        if is_terminal_status "$stack_status"; then
            log_info "Deployment reached terminal status: $stack_status"
            
            if is_failure_status "$stack_status"; then
                log_error "Deployment failed with status: $stack_status"
                log_structured "ERROR" "Deployment failed: $stack_status" "$correlation_id"
                
                # Get failure details
                local failure_events=$(AWS_PAGER="" aws cloudformation describe-stack-events \
                    --stack-name "$stack_name" \
                    --region "$REGION" \
                    --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
                    --output json 2>/dev/null || echo "[]")
                
                if [ "$(echo "$failure_events" | jq 'length')" -gt 0 ]; then
                    log_error "Failure details:"
                    echo "$failure_events" | jq -r '.[] | "  - " + .[0] + ": " + (.[1] // "No reason provided")'
                fi
                
                return 1
            else
                log_success "Deployment completed successfully: $stack_status"
                log_structured "SUCCESS" "Deployment completed: $stack_status" "$correlation_id"
                return 0
            fi
        fi
        
        # Wait before next check
        sleep $CHECK_INTERVAL
    done
}

# Handle signals for graceful shutdown
cleanup() {
    log_info "Received shutdown signal, cleaning up..."
    log_structured "INFO" "Monitoring stopped" "${CORRELATION_ID:-UNKNOWN}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Show usage
usage() {
    cat <<EOF
Usage: $0 <correlation_id> <stack_name> [slack_channel] [log_file]

Arguments:
  correlation_id    Unique identifier for this deployment
  stack_name        CloudFormation stack name to monitor
  slack_channel     Slack channel for notifications (default: #kiro-updates)
  log_file          Path to structured log file (optional)

Environment Variables:
  AWS_REGION        AWS region (default: us-east-1)
  CHECK_INTERVAL    Seconds between checks (default: 30)
  STALL_THRESHOLD   Seconds before stall alert (default: 600)
  MAX_DURATION      Seconds before duration alert (default: 2400)

Examples:
  $0 20260114-123456-abc123 CourtCaseManagementStack
  $0 20260114-123456-abc123 CourtCaseManagementStack #kiro-updates /tmp/deploy.log
EOF
}

# Main function
main() {
    if [ $# -lt 2 ]; then
        usage
        exit 1
    fi
    
    local correlation_id="$1"
    local stack_name="$2"
    local slack_channel="${3:-#kiro-updates}"
    local log_file="${4:-}"
    
    monitor_deployment "$correlation_id" "$stack_name" "$slack_channel" "$log_file"
}

# Execute main function
main "$@"
