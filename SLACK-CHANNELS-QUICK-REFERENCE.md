# Slack Channels Quick Reference

## Channel Overview

| Channel            | Purpose                           | Polling Required? | Use Case                          |
| ------------------ | --------------------------------- | ----------------- | --------------------------------- |
| **#kiro-updates**  | Status updates, progress reports  | No                | One-way informational messages    |
| **#kiro-interact** | Questions requiring user response | Yes               | Two-way interactive communication |

## When to Use Each Channel

### #kiro-updates (Status Updates)

**Use for:**

- ✅ Deployment progress updates
- ✅ System status reports
- ✅ Completion notifications
- ✅ Error alerts (informational)
- ✅ Debug information
- ✅ General progress reports

**Examples:**

```bash
# Starting a process
mcp_slack_conversations_add_message \
  --channel_id="#kiro-updates" \
  --payload="🚀 Starting deployment to production..."

# Progress update
mcp_slack_conversations_add_message \
  --channel_id="#kiro-updates" \
  --payload="⏳ Building Docker images... (2/5 complete)"

# Completion
mcp_slack_conversations_add_message \
  --channel_id="#kiro-updates" \
  --payload="✅ Deployment complete! All services healthy."

# Error notification
mcp_slack_conversations_add_message \
  --channel_id="#kiro-updates" \
  --payload="❌ Build failed: Missing environment variable"
```

### #kiro-interact (Interactive Questions)

**Use for:**

- ✅ Yes/No questions
- ✅ Multiple choice decisions
- ✅ User input requests
- ✅ Confirmation requests
- ✅ Action approvals

**IMPORTANT:** Always trigger the Slack question poller when using this channel!

**Examples:**

```bash
# Yes/No question
mcp_slack_conversations_add_message \
  --channel_id="#kiro-interact" \
  --payload="🤖 Proceed with deployment? (yes/no)"

response=$(python3 kiro_slack_poller.py "#kiro-interact" "Proceed with deployment?")

# Multiple choice
mcp_slack_conversations_add_message \
  --channel_id="#kiro-interact" \
  --payload="⚠️ Build failed. Options:\na) Retry\nb) Investigate\nc) Rollback\n\nYour choice? (a/b/c)"

choice=$(python3 kiro_slack_poller.py "#kiro-interact" "Build failed")

# Confirmation request
mcp_slack_conversations_add_message \
  --channel_id="#kiro-interact" \
  --payload="🗑️ Delete stuck CloudFormation stack? (yes/no)"

confirm=$(python3 kiro_slack_poller.py "#kiro-interact" "Delete stack?")
```

## Complete Workflow Example

### Deployment with User Interaction

```bash
#!/bin/bash

# 1. Send start notification to #kiro-updates
mcp_slack_conversations_add_message \
  --channel_id="#kiro-updates" \
  --payload="🚀 Starting deployment process..."

# 2. Build phase - status updates to #kiro-updates
mcp_slack_conversations_add_message \
  --channel_id="#kiro-updates" \
  --payload="🔨 Building Docker images..."

build_result=$(docker build .)

if [ $? -ne 0 ]; then
  # 3. Build failed - ask user in #kiro-interact
  mcp_slack_conversations_add_message \
    --channel_id="#kiro-interact" \
    --payload="❌ Build failed. Retry or investigate? (retry/investigate)"

  response=$(python3 kiro_slack_poller.py "#kiro-interact" "Build failed")

  # 4. Send user's choice confirmation to #kiro-updates
  mcp_slack_conversations_add_message \
    --channel_id="#kiro-updates" \
    --payload="✅ User chose: $response"

  if [ "$response" = "retry" ]; then
    # Retry build
    mcp_slack_conversations_add_message \
      --channel_id="#kiro-updates" \
      --payload="🔄 Retrying build..."
  else
    # Stop for investigation
    mcp_slack_conversations_add_message \
      --channel_id="#kiro-updates" \
      --payload="🔍 Pausing for investigation..."
    exit 1
  fi
fi

# 5. Build succeeded - continue with deployment
mcp_slack_conversations_add_message \
  --channel_id="#kiro-updates" \
  --payload="✅ Build successful! Deploying..."

# 6. Before production deployment - ask for confirmation
mcp_slack_conversations_add_message \
  --channel_id="#kiro-interact" \
  --payload="🚨 Ready to deploy to PRODUCTION. Proceed? (yes/no)"

deploy_confirm=$(python3 kiro_slack_poller.py "#kiro-interact" "Deploy to production?")

if [ "$deploy_confirm" = "yes" ]; then
  # 7. Deploy and send updates to #kiro-updates
  mcp_slack_conversations_add_message \
    --channel_id="#kiro-updates" \
    --payload="🚀 Deploying to production..."

  # Deploy...

  # 8. Final status to #kiro-updates
  mcp_slack_conversations_add_message \
    --channel_id="#kiro-updates" \
    --payload="🎉 Deployment complete! All services healthy."
else
  mcp_slack_conversations_add_message \
    --channel_id="#kiro-updates" \
    --payload="⏸️ Deployment cancelled by user."
fi
```

## Decision Tree

```
Need to send Slack message?
│
├─ Is it informational only?
│  └─ YES → Use #kiro-updates (no polling)
│
└─ Does it require user response?
   └─ YES → Use #kiro-interact (with polling)
```

## Common Patterns

### Pattern 1: Status Update Only

```bash
mcp_slack_conversations_add_message \
  --channel_id="#kiro-updates" \
  --payload="Your message here"
```

### Pattern 2: Question with Response

```bash
# Send question
mcp_slack_conversations_add_message \
  --channel_id="#kiro-interact" \
  --payload="Your question here? (option1/option2)"

# Poll for response
response=$(python3 kiro_slack_poller.py "#kiro-interact" "Your question")

# Confirm back to #kiro-updates
mcp_slack_conversations_add_message \
  --channel_id="#kiro-updates" \
  --payload="User responded: $response"
```

### Pattern 3: Error with Decision

```bash
# Notify error in #kiro-updates
mcp_slack_conversations_add_message \
  --channel_id="#kiro-updates" \
  --payload="❌ Error detected: $error_message"

# Ask for resolution in #kiro-interact
mcp_slack_conversations_add_message \
  --channel_id="#kiro-interact" \
  --payload="How to resolve? (retry/rollback/investigate)"

choice=$(python3 kiro_slack_poller.py "#kiro-interact" "Error resolution")

# Execute and update in #kiro-updates
mcp_slack_conversations_add_message \
  --channel_id="#kiro-updates" \
  --payload="Executing: $choice"
```

## Best Practices

1. **Always use #kiro-updates for status** - Keep users informed
2. **Always poll when using #kiro-interact** - Don't send questions without polling
3. **Confirm user responses** - Send acknowledgment back to #kiro-updates
4. **Clear questions** - Make options explicit (yes/no, a/b/c)
5. **Timeout handling** - Have a default action if polling times out

## Troubleshooting

### Message Not Appearing

**Check:**

- Channel ID is correct (use channel ID, not just name)
- Slack MCP is configured properly
- Bot has permission to post in channel

### Polling Not Detecting Response

**Check:**

- You replied in the correct channel (#kiro-interact)
- Polling script is still running
- Response was sent after the question

### Wrong Channel Used

**Fix:**

- Status updates should go to #kiro-updates
- Questions should go to #kiro-interact
- Update your scripts to use correct channel

## Summary

**Simple Rule:**

- **Tell** → #kiro-updates
- **Ask** → #kiro-interact (+ poll)

**Always remember:**

- Status updates = #kiro-updates (one-way)
- Questions = #kiro-interact (two-way with polling)
