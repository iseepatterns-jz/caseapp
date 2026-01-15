#!/bin/bash

# Slack Question Poller
# Sends a question to Slack and polls for user response for up to 15 minutes

set -euo pipefail

# Configuration
CHANNEL_ID="${SLACK_CHANNEL_ID:-#general}"
POLL_INTERVAL=30  # Check every 30 seconds
MAX_POLLS=30      # 30 polls * 30 seconds = 15 minutes
RESPONSE_FILE="/tmp/slack_response_$$.txt"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to send question to Slack
send_question() {
    local question="$1"
    local timestamp=$(date +%s)
    
    echo -e "${YELLOW}📤 Sending question to Slack...${NC}"
    echo "$question" | tee "${RESPONSE_FILE}.question"
    
    # Send to Slack using MCP
    # Note: This would be called by Kiro's MCP Slack integration
    echo "$timestamp" > "${RESPONSE_FILE}.timestamp"
    echo "$question"
}

# Function to check for new Slack messages
check_for_response() {
    local start_timestamp="$1"
    local channel="$2"
    
    # Get recent messages from Slack
    # This would use Kiro's Slack MCP to fetch messages
    # For now, we'll create a placeholder that can be integrated
    
    # Check if there are new messages after our question timestamp
    # Return 0 if response found, 1 if not
    
    # Placeholder: Check for response file (for testing)
    if [ -f "${RESPONSE_FILE}.answer" ]; then
        cat "${RESPONSE_FILE}.answer"
        return 0
    fi
    
    return 1
}

# Function to poll for response
poll_for_response() {
    local start_timestamp="$1"
    local channel="$2"
    local poll_count=0
    
    echo -e "${YELLOW}⏳ Polling for response (checking every ${POLL_INTERVAL}s for up to 15 minutes)...${NC}"
    
    while [ $poll_count -lt $MAX_POLLS ]; do
        poll_count=$((poll_count + 1))
        elapsed=$((poll_count * POLL_INTERVAL))
        minutes=$((elapsed / 60))
        seconds=$((elapsed % 60))
        
        echo -e "${YELLOW}[${minutes}m ${seconds}s] Checking for response (attempt ${poll_count}/${MAX_POLLS})...${NC}"
        
        if check_for_response "$start_timestamp" "$channel"; then
            echo -e "${GREEN}✅ Response received!${NC}"
            return 0
        fi
        
        if [ $poll_count -lt $MAX_POLLS ]; then
            sleep $POLL_INTERVAL
        fi
    done
    
    echo -e "${RED}⏰ Timeout: No response received after 15 minutes${NC}"
    return 1
}

# Main execution
main() {
    local question="${1:-Please provide input}"
    local channel="${2:-$CHANNEL_ID}"
    
    echo -e "${GREEN}=== Slack Question Poller ===${NC}"
    echo "Question: $question"
    echo "Channel: $channel"
    echo ""
    
    # Send question
    send_question "$question"
    
    # Get timestamp
    local start_timestamp=$(cat "${RESPONSE_FILE}.timestamp")
    
    # Poll for response
    if poll_for_response "$start_timestamp" "$channel"; then
        # Clean up
        rm -f "${RESPONSE_FILE}."*
        exit 0
    else
        # Clean up
        rm -f "${RESPONSE_FILE}."*
        exit 1
    fi
}

# Run if called directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
