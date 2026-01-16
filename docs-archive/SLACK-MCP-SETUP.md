# Slack MCP Server Setup Guide

## ✅ Installation Complete

The Slack MCP server has been installed and configured in your MCP settings. It's currently **disabled** until you provide the required Slack tokens.

## 🔧 Configuration Location

Your Slack MCP server is configured in: `~/.kiro/settings/mcp.json`

## 🔑 Required: Get Slack Tokens

You need to obtain Slack authentication tokens. Choose one of these methods:

### Method 1: OAuth Token (Recommended)

1. **Create a Slack App**:

   - Go to https://api.slack.com/apps
   - Click "Create New App" → "From scratch"
   - Name your app (e.g., "Kiro MCP Integration")
   - Select your workspace

2. **Configure OAuth Scopes**:

   - Go to "OAuth & Permissions" in your app settings
   - Add these Bot Token Scopes:
     - `channels:history` - Read messages in public channels
     - `channels:read` - View basic information about public channels
     - `chat:write` - Send messages
     - `users:read` - View people in the workspace
     - `users:read.email` - View email addresses of people in the workspace
     - `search:read` - Search workspace content

3. **Install App to Workspace**:
   - Click "Install to Workspace"
   - Authorize the app
   - Copy the "User OAuth Token" (starts with `xoxp-`)

### Method 2: Browser Tokens (Stealth Mode)

1. **Open Slack in Browser**:

   - Go to your Slack workspace in a web browser
   - Open Developer Tools (F12)

2. **Extract Tokens**:
   - Go to Application/Storage → Cookies
   - Find cookies for your Slack domain
   - Copy the value of the cookie starting with `xoxc-`
   - Copy the value of the cookie named `d`

## 🚀 Enable the MCP Server

Once you have your tokens, update the configuration:

### For OAuth Token (Method 1):

```bash
# Edit the MCP configuration
cat ~/.kiro/settings/mcp.json | jq '.mcpServers.slack.env.SLACK_MCP_XOXP_TOKEN = "your_actual_token_here"' | jq '.mcpServers.slack.disabled = false' > ~/.kiro/settings/mcp.json.tmp && mv ~/.kiro/settings/mcp.json.tmp ~/.kiro/settings/mcp.json
```

### For Browser Tokens (Method 2):

```bash
# Edit the MCP configuration for stealth mode
cat ~/.kiro/settings/mcp.json | jq '.mcpServers.slack.env = {
  "SLACK_MCP_XOXC_TOKEN": "your_xoxc_token_here",
  "SLACK_MCP_XOXD_TOKEN": "your_d_cookie_here",
  "SLACK_MCP_ADD_MESSAGE_TOOL": "true",
  "SLACK_MCP_LOG_LEVEL": "info"
}' | jq '.mcpServers.slack.disabled = false' > ~/.kiro/settings/mcp.json.tmp && mv ~/.kiro/settings/mcp.json.tmp ~/.kiro/settings/mcp.json
```

## 🧪 Test the Configuration

After adding your tokens, test the server:

```bash
# Test with OAuth token
SLACK_MCP_XOXP_TOKEN="your_token" npx slack-mcp-server

# Test with browser tokens
SLACK_MCP_XOXC_TOKEN="your_xoxc_token" SLACK_MCP_XOXD_TOKEN="your_d_token" npx slack-mcp-server
```

## 🔧 Available Tools

Once configured, you'll have access to these Slack tools:

- **conversations_history** - Get messages from channels/DMs
- **conversations_replies** - Get thread replies
- **conversations_search_messages** - Search messages across workspace
- **conversations_add_message** - Send messages (enabled)
- **channels_list** - List all channels

## 🛡️ Security Features

- **Safe Message Posting**: Message posting is enabled but can be restricted to specific channels
- **Cache Support**: User and channel information is cached for performance
- **Proxy Support**: Can route through proxy if needed

## 📱 Mobile Access

Once configured, you can:

1. Use Kiro to send messages to Slack channels
2. Search your Slack history for information
3. Get channel and user information
4. Reply to threads and conversations

## 🔄 Restart MCP Server

After configuration changes, the MCP server will automatically reconnect. You can also manually restart it from the Kiro MCP Server view.

## 🆘 Troubleshooting

If you encounter issues:

1. **Check token validity**:

   ```bash
   SLACK_MCP_XOXP_TOKEN="your_token" npx slack-mcp-server
   ```

2. **Verify configuration**:

   ```bash
   cat ~/.kiro/settings/mcp.json | jq '.mcpServers.slack'
   ```

3. **Check logs**: Look at the MCP Server view in Kiro for error messages

4. **Test basic functionality**:
   ```bash
   # List channels
   SLACK_MCP_XOXP_TOKEN="your_token" npx slack-mcp-server
   ```

## 📞 Next Steps

1. Get your Slack tokens using one of the methods above
2. Update the MCP configuration with your tokens
3. Enable the server by setting `disabled: false`
4. Test the connection
5. Start using Slack integration in Kiro!

---

**Note**: The server is currently disabled until you provide valid Slack tokens. This is for security - we don't want to attempt connections without proper authentication.
