#!/bin/bash
# Active monitoring for Deployment #68
# Expected duration: ~20 minutes without OpenSearch

RUN_ID="21018095187"
SLACK_CHANNEL="C0A9M9DPFUY"
START_TIME=$(date +%s)

echo "=== Deployment #68 Monitoring Started at $(date) ==="
echo "Run ID: $RUN_ID"
echo "Expected duration: ~20 minutes"
echo ""

# Monitor for up to 30 minutes (6 checks x 5 minutes)
for i in {1..6}; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    ELAPSED_MIN=$((ELAPSED / 60))
    
    echo "[Check $i at ${ELAPSED_MIN}m] Checking deployment status..."
    
    # Check GitHub Actions status
    STATUS=$(gh run view $RUN_ID --json status,conclusion 2>/dev/null || echo "error")
    
    if [ "$STATUS" = "error" ]; then
        echo "ERROR: Failed to get run status"
        sleep 60
        continue
    fi
    
    RUN_STATUS=$(echo "$STATUS" | jq -r '.status')
    RUN_CONCLUSION=$(echo "$STATUS" | jq -r '.conclusion')
    
    echo "  Status: $RUN_STATUS"
    echo "  Conclusion: $RUN_CONCLUSION"
    
    # Check if completed
    if [ "$RUN_STATUS" = "completed" ]; then
        echo ""
        echo "=== Deployment completed at ${ELAPSED_MIN}m ==="
        echo "Conclusion: $RUN_CONCLUSION"
        
        if [ "$RUN_CONCLUSION" = "success" ]; then
            echo "✅ DEPLOYMENT SUCCESSFUL"
            exit 0
        else
            echo "❌ DEPLOYMENT FAILED"
            exit 1
        fi
    fi
    
    # Check ECS monitor log for issues
    if [ -f ecs-monitor.log ]; then
        if grep -q "SECRET ERROR" ecs-monitor.log; then
            echo "⚠️  SECRET ERROR detected in ECS monitor"
        fi
        if grep -q "STOPPED" ecs-monitor.log; then
            echo "⚠️  ECS tasks STOPPED detected"
        fi
    fi
    
    # Send Slack update every 10 minutes (every 2 checks)
    if [ $((i % 2)) -eq 0 ]; then
        echo "  Sending Slack update..."
    fi
    
    # Wait 5 minutes before next check
    if [ $i -lt 6 ]; then
        echo "  Waiting 5 minutes..."
        sleep 300
    fi
done

echo ""
echo "=== Monitoring timeout after 30 minutes ==="
echo "Deployment may still be in progress"
exit 2
