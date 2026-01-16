#!/bin/bash

# Monitor deployment and send Slack notification when complete
WORKFLOW_ID="20963788185"
REPO="iseepatterns-jz/caseapp"

echo "🔄 Monitoring deployment workflow ID: $WORKFLOW_ID"
echo "Started at: $(date)"

while true; do
    # Get current status
    STATUS=$(gh run list --repo "$REPO" --limit 1 --json status,conclusion --jq '.[0]')
    CURRENT_STATUS=$(echo "$STATUS" | jq -r '.status')
    CONCLUSION=$(echo "$STATUS" | jq -r '.conclusion // "running"')
    
    echo "$(date): Status = $CURRENT_STATUS, Conclusion = $CONCLUSION"
    
    # Check if workflow is complete
    if [ "$CURRENT_STATUS" = "completed" ]; then
        echo "✅ Deployment completed with conclusion: $CONCLUSION"
        break
    fi
    
    # Wait 30 seconds before checking again
    sleep 30
done

echo "🎉 Deployment monitoring complete!"
echo "Final status: $CURRENT_STATUS"
echo "Final conclusion: $CONCLUSION"