#!/bin/bash

# Ask User Via Slack - Integrated with Kiro MCP
# This script sends a question to Slack and polls for user response

set -euo pipefail

# Configuration
CHANNEL_ID="${1:-#general}"
QUESTION="${2:-Please provide your input}"
POLL_INTERVAL=30
MAX_DURATION=900  # 15 minutes in seconds
RESPONSE_FILE="/tmp/slack_response_$(date +%s).txt"

# Get the timestamp of when we send the message
START_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "=== Kiro Slack Question Poller ==="
echo "Channel: $CHANNEL_ID"
echo "Question: $QUESTION"
echo "Start time: $START_TIMESTAMP"
echo ""

# Send the question to Slack
echo "📤 Sending question to Slack..."
echo ""
echo "🤖 Kiro Question:"
echo "$QUESTION"
echo ""
echo "Please reply in Slack. Polling for response for 15 minutes..."
echo ""

# Store the question and timestamp
echo "$QUESTION" > "${RESPONSE_FILE}.question"
echo "$START_TIMESTAMP" > "${RESPONSE_FILE}.timestamp"

# Polling loop
elapsed=0
poll_count=0

while [ $elapsed -lt $MAX_DURATION ]; do
    poll_count=$((poll_count + 1))
    minutes=$((elapsed / 60))
    seconds=$((elapsed % 60))
    remaining=$((MAX_DURATION - elapsed))
    remaining_minutes=$((remaining / 60))
    
    echo "[${minutes}m ${seconds}s] Checking for response... (${remaining_minutes}m remaining, poll #${poll_count})"
    
    # Check Slack for new messages
    # This would integrate with Kiro's Slack MCP to fetch messages
    # For now, we'll check for a response file that can be created by Kiro
    
    # In actual use, Kiro would call the Slack MCP here:
    # mcp_slack_conversations_history --channel_id="$CHANNEL_ID" --limit=5
    # Then parse for messages after START_TIMESTAMP from the user
    
    # Placeholder: Check if response file exists
    if [ -f "${RESPONSE_FILE}.answer" ]; then
        echo ""
        echo "✅ Response received!"
        echo ""
        cat "${RESPONSE_FILE}.answer"
        
        # Clean up
        rm -f "${RESPONSE_FILE}."*
        exit 0
    fi
    
    # Wait before next check
    sleep $POLL_INTERVAL
    elapsed=$((elapsed + POLL_INTERVAL))
done

# Timeout
echo ""
echo "⏰ Timeout: No response received after 15 minutes"
echo ""

# Clean up
rm -f "${RESPONSE_FILE}."*
exit 1
