#!/bin/bash

# Script to join bot to all channels
BOT_TOKEN="xoxb-8864871929959-10291712266340-Wb5PkyIjECWohShdoXdKCaFK"

echo "Joining bot to channels..."

# Join #aws-alarms
echo "Joining #aws-alarms..."
curl -X POST https://slack.com/api/conversations.join \
  -H "Authorization: Bearer $BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel": "C0A3B5BBZH9"}'

echo ""

# Join #all-iseepatterns  
echo "Joining #all-iseepatterns..."
curl -X POST https://slack.com/api/conversations.join \
  -H "Authorization: Bearer $BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel": "C08RERN3GHM"}'

echo ""

# Join #n8n-error
echo "Joining #n8n-error..."
curl -X POST https://slack.com/api/conversations.join \
  -H "Authorization: Bearer $BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel": "C08RYDVM0F6"}'

echo ""

echo "Bot should now be able to send messages to channels!"