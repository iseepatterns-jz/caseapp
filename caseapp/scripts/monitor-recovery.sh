#!/bin/bash
#
# Monitor Recovery Script
# Detects when monitor process crashes and automatically restarts it
#
# Usage: bash monitor-recovery.sh <correlation_id> <stack_name> <slack_channel> <log_file>
#

set -euo pipefail

# Configuration
CORRELATION_ID="${1:-}"
STACK_NAME="${2:-}"
SLACK_CHANNEL="${3:-#kiro-updates}"
LOG_FILE="${4:-deployment-monitor.log}"
RECOVERY_LOG="monitor-recovery.log"
CHECK_INTERVAL=60  # Check every 60 seconds
MAX_RESTARTS=5     # Maximum restart attempts
RESTART_WINDOW=300 # 5 minutes window for restart counting

# Validate required parameters
if [ -z "$CORRELATION_ID" ] || [ -z "$STACK_NAME" ]; then
    echo "Usage: $0 <correlation_id> <stack_name> [slack_channel] [log_file]"
    exit 1
fi

# Initialize restart tracking
RESTART_COUNT=0
LAST_RESTART_TIME=0

# Function to log recovery events
log_recovery() {
    local message="$1"
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S UTC")] [RECOVERY] $message" | tee -a "$RECOVERY_LOG"
}

# Function to send Slack alert
send_slack_alert() {
    local message="$1"
    bash "$(dirname "$0")/slack-notifier.sh" monitoring_alert \
        "$CORRELATION_ID" "$STACK_NAME" "$message" 2>/dev/null || true
}

# Function to check if monitor is running
is_monitor_running() {
    pgrep -f "deployment-monitor.sh.*$CORRELATION_ID" > /dev/null 2>&1
}

# Function to restart monitor
restart_monitor() {
    local current_time=$(date +%s)
    
    # Check if we're within the restart window
    if [ $((current_time - LAST_RESTART_TIME)) -lt $RESTART_WINDOW ]; then
        RESTART_COUNT=$((RESTART_COUNT + 1))
    else
        # Reset counter if outside window
        RESTART_COUNT=1
    fi
    
    LAST_RESTART_TIME=$current_time
    
    # Check if we've exceeded max restarts
    if [ $RESTART_COUNT -gt $MAX_RESTARTS ]; then
        log_recovery "ERROR: Exceeded maximum restart attempts ($MAX_RESTARTS) within $RESTART_WINDOW seconds"
        send_slack_alert "🚨 Monitor recovery failed: Too many restarts. Manual intervention required."
        return 1
    fi
    
    log_recovery "Restarting monitor (attempt $RESTART_COUNT/$MAX_RESTARTS)..."
    
    # Start monitor in background
    nohup bash "$(dirname "$0")/deployment-monitor.sh" \
        "$CORRELATION_ID" "$STACK_NAME" "$SLACK_CHANNEL" "$LOG_FILE" \
        >> "$LOG_FILE" 2>&1 &
    
    local monitor_pid=$!
    
    # Wait a few seconds and verify it started
    sleep 5
    
    if is_monitor_running; then
        log_recovery "Monitor restarted successfully (PID: $monitor_pid)"
        send_slack_alert "✅ Monitor recovered automatically (restart #$RESTART_COUNT)"
        return 0
    else
        log_recovery "ERROR: Monitor failed to start"
        send_slack_alert "🚨 Monitor restart failed. Manual intervention required."
        return 1
    fi
}

# Function to check deployment completion
is_deployment_complete() {
    local stack_status=$(AWS_PAGER="" aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "UNKNOWN")
    
    case "$stack_status" in
        CREATE_COMPLETE|UPDATE_COMPLETE|DELETE_COMPLETE)
            return 0
            ;;
        CREATE_FAILED|UPDATE_FAILED|DELETE_FAILED|ROLLBACK_COMPLETE|ROLLBACK_FAILED|UPDATE_ROLLBACK_COMPLETE|UPDATE_ROLLBACK_FAILED)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Main recovery loop
log_recovery "Starting monitor recovery for deployment $CORRELATION_ID"
log_recovery "Stack: $STACK_NAME, Log: $LOG_FILE"

while true; do
    # Check if deployment is complete
    if is_deployment_complete; then
        log_recovery "Deployment completed. Stopping recovery monitoring."
        break
    fi
    
    # Check if monitor is running
    if ! is_monitor_running; then
        log_recovery "Monitor process not found. Initiating recovery..."
        send_slack_alert "⚠️ Monitor process crashed. Attempting automatic recovery..."
        
        if ! restart_monitor; then
            log_recovery "Recovery failed. Exiting."
            exit 1
        fi
    fi
    
    # Wait before next check
    sleep $CHECK_INTERVAL
done

log_recovery "Monitor recovery completed successfully"
exit 0
