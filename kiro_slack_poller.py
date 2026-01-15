#!/usr/bin/env python3
"""
Kiro Slack Question Poller
Sends a question to Slack and polls for user response for 15 minutes
Designed to be called by Kiro when it needs user input
"""

import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
POLL_INTERVAL = 30  # seconds
MAX_DURATION = 900  # 15 minutes
RESPONSE_DIR = Path("/tmp/kiro_slack_responses")
RESPONSE_DIR.mkdir(exist_ok=True)


def log(message):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def send_question_to_slack(channel, question):
    """
    Send question to Slack via Kiro MCP
    Returns the message timestamp for tracking
    """
    log(f"📤 Sending question to Slack channel: {channel}")
    log(f"Question: {question}")
    
    # Format message with clear call to action
    formatted_message = (
        f"🤖 **Kiro has a question:**\n\n"
        f"{question}\n\n"
        f"_Please reply in this channel. I'll check for your response for the next 15 minutes._"
    )
    
    # This would be executed by Kiro using its Slack MCP
    # For now, output the command that should be run
    command = {
        "tool": "mcp_slack_conversations_add_message",
        "params": {
            "channel_id": channel,
            "payload": formatted_message,
            "content_type": "text/markdown"
        }
    }
    
    log(f"Slack command: {json.dumps(command, indent=2)}")
    
    # Return current timestamp for filtering responses
    return datetime.utcnow().isoformat() + "Z"


def check_for_response(channel, since_timestamp, session_id):
    """
    Check Slack for user responses after the question timestamp
    Returns response text if found, None otherwise
    """
    # Check if response file exists (for testing/manual input)
    response_file = RESPONSE_DIR / f"response_{session_id}.txt"
    if response_file.exists():
        response = response_file.read_text().strip()
        log(f"✅ Found response in file: {response}")
        response_file.unlink()  # Clean up
        return response
    
    # This would use Kiro's Slack MCP to fetch recent messages
    # For actual implementation, Kiro would execute:
    # mcp_slack_conversations_history(channel_id=channel, limit=10)
    # Then filter for messages after since_timestamp from the user
    
    command = {
        "tool": "mcp_slack_conversations_history",
        "params": {
            "channel_id": channel,
            "limit": 10
        }
    }
    
    # In actual use, Kiro would:
    # 1. Execute the above command
    # 2. Parse the response
    # 3. Filter for messages after since_timestamp
    # 4. Return the first user message found
    
    return None


def poll_for_response(channel, since_timestamp, session_id):
    """
    Poll Slack for user response with timeout
    Returns response text or None if timeout
    """
    log(f"⏳ Starting polling loop (15 minute timeout)")
    log(f"Checking every {POLL_INTERVAL} seconds")
    log(f"Session ID: {session_id}")
    
    start_time = time.time()
    poll_count = 0
    
    while True:
        elapsed = time.time() - start_time
        
        if elapsed >= MAX_DURATION:
            log("⏰ Timeout: No response received after 15 minutes")
            return None
        
        poll_count += 1
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        remaining = MAX_DURATION - elapsed
        remaining_minutes = int(remaining // 60)
        
        log(f"[{minutes}m {seconds}s] Poll #{poll_count} ({remaining_minutes}m remaining)")
        
        # Check for response
        response = check_for_response(channel, since_timestamp, session_id)
        
        if response:
            log(f"✅ Response received: {response}")
            return response
        
        # Wait before next poll
        time.sleep(POLL_INTERVAL)


def main():
    """Main execution"""
    if len(sys.argv) < 3:
        print("Usage: python3 kiro_slack_poller.py <channel> <question>")
        print('Example: python3 kiro_slack_poller.py "#general" "Should I proceed with deployment?"')
        sys.exit(1)
    
    channel = sys.argv[1]
    question = " ".join(sys.argv[2:])
    
    # Generate session ID
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    log("=== Kiro Slack Question Session ===")
    log(f"Channel: {channel}")
    log(f"Session: {session_id}")
    print()
    
    # Send question
    start_timestamp = send_question_to_slack(channel, question)
    print()
    
    # Create info file for manual testing
    info_file = RESPONSE_DIR / f"session_{session_id}.json"
    info_file.write_text(json.dumps({
        "session_id": session_id,
        "channel": channel,
        "question": question,
        "start_timestamp": start_timestamp,
        "response_file": str(RESPONSE_DIR / f"response_{session_id}.txt")
    }, indent=2))
    
    log(f"💡 For testing: echo 'your response' > {RESPONSE_DIR}/response_{session_id}.txt")
    print()
    
    # Poll for response
    response = poll_for_response(channel, start_timestamp, session_id)
    
    # Clean up
    if info_file.exists():
        info_file.unlink()
    
    if response:
        log("=== Session completed successfully ===")
        print()
        print("USER RESPONSE:")
        print(response)
        sys.exit(0)
    else:
        log("=== Session timed out ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
