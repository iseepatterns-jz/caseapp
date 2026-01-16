#!/bin/bash

# Kiro Slack Question Integration
# This script is designed to be called by Kiro when it needs user input via Slack

set -euo pipefail

# Configuration
CHANNEL_ID="${SLACK_CHANNEL_ID:-#general}"
POLL_INTERVAL=30  # Check every 30 seconds
MAX_POLLS=30      # 30 polls * 30 seconds = 15 minutes
RESPONSE_LOG="/tmp/kiro_slack_response_$(date +%s).log"

# Function to log
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$RESPONSE_LOG"
}

# Function to send question via Kiro's Slack MCP
send_slack_question() {
    local question="$1"
    local channel="$2"
    
    log "📤 Sending question to Slack channel: $channel"
    log "Question: $question"
    
    # This will be integrated with Kiro's MCP Slack tool
    # For now, output the command that Kiro should execute
    cat << EOF
{
  "action": "send_message",
  "channel": "$channel",
  "message": "🤖 **Kiro has a question:**\n\n$question\n\n_Please reply in this thread. I'll check for your response for the next 15 minutes._"
}
EOF
}

# Function to check Slack for responses
check_slack_response() {
    local channel="$1"
    local since_timestamp="$2"
    
    # This will use Kiro's Slack MCP to fetch recent messages
    # Returns the latest message from the user after the timestamp
    cat << EOF
{
  "action": "check_messages",
  "channel": "$channel",
  "since": "$since_timestamp",
  "limit": 5
}
EOF
}

# Main polling loop
poll_for_slack_response() {
    local channel="$1"
    local start_time=$(date +%s)
    local poll_count=0
    
    log "⏳ Starting polling loop (15 minute timeout)"
    
    while [ $poll_count -lt $MAX_POLLS ]; do
        poll_count=$((poll_count + 1))
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))
        minutes=$((elapsed / 60))
        seconds=$((elapsed % 60))
        remaining_polls=$((MAX_POLLS - poll_count))
        
        log "[${minutes}m ${seconds}s] Poll attempt ${poll_count}/${MAX_POLLS} (${remaining_polls} remaining)"
        
        # Check for response
        # In actual implementation, this would call Kiro's Slack MCP
        response=$(check_slack_response "$channel" "$start_time")
        
        # Parse response (this is a placeholder)
        # In real implementation, Kiro would parse the MCP response
        if [ -f "/tmp/slack_user_response.txt" ]; then
            user_response=$(cat /tmp/slack_user_response.txt)
            log "✅ Response received: $user_response"
            echo "$user_response"
            rm -f /tmp/slack_user_response.txt
            return 0
        fi
        
        # Wait before next poll
        if [ $poll_count -lt $MAX_POLLS ]; then
            sleep $POLL_INTERVAL
        fi
    done
    
    log "⏰ Timeout: No response received after 15 minutes"
    return 1
}

# Main function
main() {
    local question="${1:-}"
    local channel="${2:-$CHANNEL_ID}"
    
    if [ -z "$question" ]; then
        echo "Usage: $0 <question> [channel]"
        echo "Example: $0 'Should I proceed with deployment?' '#general'"
        exit 1
    fi
    
    log "=== Kiro Slack Question Session Started ==="
    log "Channel: $channel"
    
    # Send question
    send_slack_question "$question" "$channel"
    
    # Poll for response
    if poll_for_slack_response "$channel"; then
        log "=== Session completed successfully ==="
        exit 0
    else
        log "=== Session timed out ==="
        exit 1
    fi
}

# Execute
main "$@"
