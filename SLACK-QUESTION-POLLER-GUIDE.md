65 # Kiro Slack Question Poller

## Overview

This system allows Kiro to ask you questions via Slack and wait for your response for up to 15 minutes. It's perfect for scenarios where Kiro needs user input during long-running tasks.

## How It Works

1. **Kiro sends a question** to your Slack channel
2. **Polling starts** - checks every 30 seconds for your response
3. **You reply in Slack** within 15 minutes
4. **Kiro receives your response** and continues execution

## Files Created

- `kiro_slack_poller.py` - Main Python script (recommended)
- `ask-user-via-slack.sh` - Bash version
- `kiro-slack-question.sh` - Alternative bash implementation
- `slack-question-poller.sh` - Basic polling script

## Usage

### Option 1: Python Script (Recommended)

```bash
python3 kiro_slack_poller.py "#general" "Should I proceed with deployment?"
```

### Option 2: Bash Script

```bash
bash ask-user-via-slack.sh "#general" "Should I proceed with deployment?"
```

## Integration with Kiro

### When Kiro Needs User Input

When I (Kiro) need your input, I can:

1. **Call the poller script**:

   ```bash
   python3 kiro_slack_poller.py "#general" "Deploy to production? (yes/no)"
   ```

2. **Send question to Slack** via MCP:

   ```
   mcp_slack_conversations_add_message(
       channel_id="#general",
       payload="🤖 Kiro Question: Deploy to production? (yes/no)"
   )
   ```

3. **Poll for your response** every 30 seconds

4. **Receive your answer** and continue

### Example Workflow

```
Kiro: "I'm about to deploy. Should I proceed?"
  ↓
Sends to Slack: "🤖 Kiro has a question: Should I proceed with deployment?"
  ↓
Polls every 30s for 15 minutes
  ↓
You reply in Slack: "Yes, proceed"
  ↓
Kiro receives: "Yes, proceed"
  ↓
Kiro continues: "Great! Starting deployment..."
```

## Testing the Poller

### Manual Testing

1. **Start the poller**:

   ```bash
   python3 kiro_slack_poller.py "#general" "Test question"
   ```

2. **In another terminal, simulate a response**:

   ```bash
   echo "Yes, proceed" > /tmp/kiro_slack_responses/response_YYYYMMDD_HHMMSS.txt
   ```

   (Use the session ID shown in the poller output)

3. **Poller will detect the response** and exit successfully

### With Actual Slack Integration

When Kiro runs this with full Slack MCP integration:

1. Question appears in your Slack channel
2. You reply in Slack
3. Kiro's MCP fetches your message
4. Poller detects your response
5. Execution continues

## Configuration

### Environment Variables

```bash
# Set default channel
export SLACK_CHANNEL_ID="#general"

# Adjust polling interval (seconds)
export POLL_INTERVAL=30

# Adjust timeout (seconds)
export MAX_DURATION=900  # 15 minutes
```

### Customization

Edit `kiro_slack_poller.py` to change:

- `POLL_INTERVAL = 30` - How often to check (seconds)
- `MAX_DURATION = 900` - Total timeout (seconds)
- Message formatting
- Response parsing logic

## Use Cases

### 1. Deployment Confirmation

```python
response = poll_slack_question(
    "#deployments",
    "Ready to deploy v2.0 to production? (yes/no)"
)

if response.lower() == "yes":
    deploy_to_production()
```

### 2. Error Resolution

```python
response = poll_slack_question(
    "#alerts",
    "Deployment failed. Should I: (a) retry, (b) rollback, (c) investigate?"
)

if response == "a":
    retry_deployment()
elif response == "b":
    rollback()
```

### 3. Resource Cleanup

```python
response = poll_slack_question(
    "#ops",
    "Found stuck CloudFormation stack. Delete it? (yes/no)"
)

if response.lower() == "yes":
    delete_stack()
```

### 4. Multi-Step Workflows

```python
# Step 1: Ask about deployment
deploy_response = poll_slack_question(
    "#general",
    "Deploy backend first or frontend first? (backend/frontend)"
)

# Step 2: Execute based on response
if deploy_response == "backend":
    deploy_backend()
    # Ask follow-up
    frontend_response = poll_slack_question(
        "#general",
        "Backend deployed. Deploy frontend now? (yes/no)"
    )
```

## Integration with Kiro Hooks

### Create a Hook for Questions

You can create an agent hook that:

1. **Triggers**: When Kiro needs user input
2. **Action**: Runs the poller script
3. **Result**: Continues execution with user's response

### Hook Configuration Example

```json
{
  "name": "Ask User via Slack",
  "trigger": "on_agent_needs_input",
  "action": {
    "type": "execute_command",
    "command": "python3 kiro_slack_poller.py '#general' '${question}'"
  }
}
```

## Slack MCP Integration

### Required Slack MCP Tools

The poller uses these Slack MCP tools:

1. **mcp_slack_conversations_add_message** - Send question
2. **mcp_slack_conversations_history** - Check for responses

### Message Format

Questions are sent as:

```
🤖 **Kiro has a question:**

[Your question here]

_Please reply in this channel. I'll check for your response for the next 15 minutes._
```

### Response Detection

The poller looks for:

- Messages in the specified channel
- Posted after the question timestamp
- From the user (not from bots)
- Within the 15-minute window

## Troubleshooting

### Poller Times Out

**Problem**: No response detected after 15 minutes

**Solutions**:

- Check Slack channel is correct
- Verify you replied in the right channel
- Ensure Slack MCP is configured correctly
- Check `/tmp/kiro_slack_responses/` for session files

### Response Not Detected

**Problem**: You replied but poller didn't see it

**Solutions**:

- Verify Slack MCP has read permissions
- Check the channel ID is correct (use `#channel-name` format)
- Ensure you replied after the question was sent
- Check Slack MCP logs for errors

### Script Errors

**Problem**: Script fails to run

**Solutions**:

- Ensure Python 3 is installed: `python3 --version`
- Check file permissions: `chmod +x kiro_slack_poller.py`
- Verify Slack MCP is configured in Kiro
- Check `/tmp/kiro_slack_responses/` directory exists

## Advanced Usage

### Custom Timeout

```bash
# 5 minute timeout instead of 15
python3 kiro_slack_poller.py "#general" "Quick question?" --timeout 300
```

### Multiple Questions

```bash
# Ask multiple questions in sequence
python3 kiro_slack_poller.py "#general" "Question 1?"
python3 kiro_slack_poller.py "#general" "Question 2?"
python3 kiro_slack_poller.py "#general" "Question 3?"
```

### Conditional Logic

```bash
response=$(python3 kiro_slack_poller.py "#general" "Proceed? (yes/no)")

if [ "$response" = "yes" ]; then
    echo "User approved, continuing..."
else
    echo "User declined, stopping..."
    exit 1
fi
```

## Best Practices

1. **Clear Questions**: Ask specific, actionable questions
2. **Provide Options**: Give clear choices (yes/no, a/b/c)
3. **Set Context**: Explain why you're asking
4. **Reasonable Timeouts**: 15 minutes is usually enough
5. **Fallback Plans**: Have a default action if timeout occurs

## Future Enhancements

Potential improvements:

- [ ] Support for threaded replies
- [ ] Multiple response formats (buttons, dropdowns)
- [ ] Response validation
- [ ] Retry logic for failed polls
- [ ] Integration with Kiro's native input system
- [ ] Support for multiple users responding
- [ ] Response history and logging

## Summary

The Slack Question Poller enables bidirectional communication between Kiro and users via Slack. It's perfect for:

- Getting deployment approvals
- Resolving ambiguous situations
- Confirming destructive actions
- Gathering user preferences
- Interactive troubleshooting

The system polls for 15 minutes, checking every 30 seconds, giving you plenty of time to respond while keeping Kiro's workflow moving.
