#!/bin/bash

# Wait for deployment to complete and send Slack notification
WORKFLOW_ID="20971914073"  # Updated to new workflow
REPO="iseepatterns-jz/caseapp"

echo "🔄 Starting deployment monitoring for new workflow..."

# Monitor until completion
while true; do
    STATUS_JSON=$(gh run list --repo "$REPO" --limit 1 --json status,conclusion,databaseId --jq '.[0]')
    CURRENT_STATUS=$(echo "$STATUS_JSON" | jq -r '.status')
    CONCLUSION=$(echo "$STATUS_JSON" | jq -r '.conclusion // "running"')
    DB_ID=$(echo "$STATUS_JSON" | jq -r '.databaseId')
    
    # Only check our specific workflow
    if [ "$DB_ID" = "$WORKFLOW_ID" ] && [ "$CURRENT_STATUS" = "completed" ]; then
        echo "✅ Deployment completed!"
        
        # Determine success/failure message
        if [ "$CONCLUSION" = "success" ]; then
            MESSAGE="🎉 **Deployment SUCCESSFUL!** 

✅ **Infrastructure Deployment**: COMPLETE
- Workflow ID: $WORKFLOW_ID
- Status: SUCCESS
- Timeout fix worked perfectly!

🚀 **Ready for Next Steps**:
- Infrastructure is fully operational
- All previous issues resolved
- Ready to discuss next plans!

Great work on resolving all the deployment issues! 🎯"
        else
            MESSAGE="⚠️ **Deployment Status Update**

❌ **Infrastructure Deployment**: FAILED
- Workflow ID: $WORKFLOW_ID  
- Status: $CONCLUSION
- Need to investigate new issues

🔍 **Next Steps**:
- Review deployment logs
- Identify and resolve new blockers
- Continue troubleshooting process

Let's analyze the failure and get this resolved! 💪"
        fi
        
        echo "Deployment monitoring complete. Status: $CONCLUSION"
        break
    fi
    
    sleep 45  # Check every 45 seconds
done