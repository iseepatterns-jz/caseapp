# Deployment Coordination Guide

## Overview

This guide explains the deployment coordination system that prevents concurrent deployments, provides real-time monitoring, and ensures reliable deployments with automatic error recovery.

## System Components

### 1. Deployment Coordinator (`deployment-coordinator.sh`)

Manages deployment queuing and prevents concurrent deployments.

**Key Functions:**

- `can_deploy` - Checks if deployment can proceed
- `register` - Registers a new deployment
- `wait` - Waits for active deployment to complete
- `cleanup` - Removes deployment from registry
- `get_active` - Gets active deployment information

**Usage:**

```bash
# Check if deployment can proceed
bash caseapp/scripts/deployment-coordinator.sh can_deploy production

# Register a deployment
bash caseapp/scripts/deployment-coordinator.sh register \
  "20260114-123456-abc123" "12345" "production"

# Wait for active deployment
bash caseapp/scripts/deployment-coordinator.sh wait production 1800

# Cleanup after deployment
bash caseapp/scripts/deployment-coordinator.sh cleanup "20260114-123456-abc123"
```

### 2. Deployment Monitor (`deployment-monitor.sh`)

Monitors CloudFormation stack events in real-time and sends progress updates.

**Features:**

- Polls stack events every 30 seconds
- Detects deployment stalls (no events for 10+ minutes)
- Sends Slack notifications for progress and issues
- Automatically exits when deployment completes

**Usage:**

```bash
# Start monitoring in background
nohup bash caseapp/scripts/deployment-monitor.sh \
  "20260114-123456-abc123" \
  "CourtCaseManagementStack" \
  "C0A9M9DPFUY" \
  "deployment-monitor.log" \
  >> deployment-monitor.log 2>&1 &
```

### 3. Slack Notifier (`slack-notifier.sh`)

Sends structured notifications to Slack channels with automatic retry.

**Notification Types:**

- `start` - Deployment started
- `concurrent` - Concurrent deployment detected
- `progress` - Deployment progress update
- `complete` - Deployment successful
- `failed` - Deployment failed
- `stalled` - Deployment stalled

**Usage:**

```bash
# Notify deployment start
bash caseapp/scripts/slack-notifier.sh start \
  "20260114-123456-abc123" "production" "12345"

# Notify deployment complete
bash caseapp/scripts/slack-notifier.sh complete \
  "20260114-123456-abc123" "production" "25" "http://app.example.com"
```

### 4. Monitor Recovery (`monitor-recovery.sh`)

Automatically restarts crashed monitoring processes.

**Features:**

- Detects monitor process crashes
- Restarts with same parameters
- Tracks restart attempts (max 5 in 5 minutes)
- Sends Slack alerts about recovery

**Usage:**

```bash
# Start recovery monitoring
bash caseapp/scripts/monitor-recovery.sh \
  "20260114-123456-abc123" \
  "CourtCaseManagementStack" \
  "C0A9M9DPFUY" \
  "deployment-monitor.log"
```

### 5. Slack Retry Queue (`slack-retry-queue.sh`)

Queues failed Slack notifications for retry with exponential backoff.

**Features:**

- Automatic queuing of failed notifications
- Exponential backoff (5s, 10s, 20s, 40s, 80s)
- Max 5 retry attempts
- Dead letter queue for permanent failures

**Usage:**

```bash
# Queue a failed notification
bash caseapp/scripts/slack-retry-queue.sh queue start \
  "20260114-123456-abc123" "production" "12345"

# Process retry queue
bash caseapp/scripts/slack-retry-queue.sh process

# Check queue status
bash caseapp/scripts/slack-retry-queue.sh status
```

### 6. Registry Fallback (`registry-fallback.sh`)

Provides coordination when deployment registry is unavailable.

**Features:**

- Falls back to CloudFormation-only coordination
- Estimates deployment progress from stack events
- Logs registry unavailability
- Continues with reduced features

**Usage:**

```bash
# Check deployment status (fallback mode)
bash caseapp/scripts/registry-fallback.sh can_deploy production

# Get active deployment (fallback mode)
bash caseapp/scripts/registry-fallback.sh get_active
```

### 7. Deployment Time Estimator (`deployment-time-estimator.sh`)

Estimates deployment completion time based on historical data.

**Features:**

- Collects historical deployment durations
- Calculates resource-specific timing
- Provides confidence intervals (±20%)
- Updates estimates in real-time

**Usage:**

```bash
# Collect historical data
bash caseapp/scripts/deployment-time-estimator.sh collect

# Estimate completion time
bash caseapp/scripts/deployment-time-estimator.sh estimate \
  "20260114-123456-abc123" "CourtCaseManagementStack" "15"

# Update history with completed deployment
bash caseapp/scripts/deployment-time-estimator.sh update \
  "20260114-123456-abc123" "25"
```

## Deployment Workflow

### Normal Deployment Flow

```
1. GitHub Actions triggered
   ↓
2. Generate correlation ID
   ↓
3. Check if deployment can proceed (deployment-coordinator.sh can_deploy)
   ↓
4. If active deployment detected:
   - Send concurrent notification
   - Wait for active deployment to complete
   ↓
5. Register deployment (deployment-coordinator.sh register)
   ↓
6. Send start notification (slack-notifier.sh start)
   ↓
7. Start monitoring (deployment-monitor.sh in background)
   ↓
8. Start monitor recovery (monitor-recovery.sh in background)
   ↓
9. Run CDK deployment
   ↓
10. Monitor sends progress updates every 10 minutes
    ↓
11. Deployment completes (success or failure)
    ↓
12. Send completion notification (slack-notifier.sh complete/failed)
    ↓
13. Cleanup deployment registry (deployment-coordinator.sh cleanup)
    ↓
14. Update deployment history (deployment-time-estimator.sh update)
```

### Concurrent Deployment Handling

When a deployment is triggered while another is active:

```
1. New deployment checks can_deploy
   ↓
2. Active deployment detected
   ↓
3. Send concurrent notification with:
   - Active deployment status
   - Elapsed time
   - Estimated remaining time
   ↓
4. Wait for active deployment (poll every 30 seconds)
   ↓
5. Active deployment completes
   ↓
6. New deployment proceeds
```

### Error Recovery

**Monitor Process Crashes:**

```
1. Monitor-recovery detects crash
   ↓
2. Send Slack alert
   ↓
3. Restart monitor with same parameters
   ↓
4. Continue monitoring
```

**Slack Notification Failures:**

```
1. Notification fails
   ↓
2. Queue for retry (slack-retry-queue.sh)
   ↓
3. Retry with exponential backoff
   ↓
4. Max 5 attempts
   ↓
5. Move to dead letter queue if all fail
```

**Registry Unavailable:**

```
1. Coordinator detects registry unavailable
   ↓
2. Log warning
   ↓
3. Fall back to CloudFormation-only coordination
   ↓
4. Continue with reduced features
```

## Slack Notifications

### Channel Usage

- **#kiro-updates** (C0A9M9DPFUY) - Status updates, progress reports
- **#kiro-interact** (C0A95T7UU4R) - Questions requiring user response

### Notification Format

**Deployment Started:**

```
🚀 **Deployment Started**

**Environment:** production
**Correlation ID:** `20260114-123456-abc123`
**Started:** 2026-01-14 12:34:56 UTC
**Workflow:** https://github.com/owner/repo/actions/runs/12345

Monitoring deployment progress...
```

**Deployment Queued:**

```
⏸️ **Deployment Queued**

**Environment:** production
**Correlation ID:** `20260114-123456-abc123`

**Active Deployment Detected:**
- Status: CREATE_IN_PROGRESS
- Started: 2026-01-14 12:00:00 UTC
- Elapsed: 15 minutes
- Estimated Remaining: 10 minutes

This deployment will wait for the active deployment to complete.
```

**Deployment Progress:**

```
⏳ **Deployment Progress Update**

**Correlation ID:** `20260114-123456-abc123`
**Status:** CREATE_IN_PROGRESS
**Time:** 2026-01-14 12:44:56 UTC
**Estimated Remaining:** 10 minutes
**Est. Completion:** 2026-01-14 12:54:56 UTC

Creating RDS instance...
```

**Deployment Complete:**

```
✅ **Deployment Successful**

**Environment:** production
**Correlation ID:** `20260114-123456-abc123`
**Completed:** 2026-01-14 12:59:56 UTC
**Duration:** 25 minutes

**Application URL:** http://app.example.com

All services are healthy and running! 🎉
```

**Deployment Failed:**

```
❌ **Deployment Failed**

**Environment:** production
**Correlation ID:** `20260114-123456-abc123`
**Failed:** 2026-01-14 12:45:00 UTC

**Error Details:**
RDS instance creation failed: Insufficient capacity

**Troubleshooting:**
- View stack events: [AWS Console Link]
- Check CloudWatch logs for detailed error messages
- Review recent code changes

Need help? Check the deployment troubleshooting guide.
```

## Correlation IDs

Every deployment has a unique correlation ID for tracing.

**Format:** `YYYYMMDD-HHMMSS-random`
**Example:** `20260114-123456-abc123`

**Usage:**

- Track deployment across all systems
- Search logs and notifications
- Query deployment history
- Troubleshoot issues

**Where to Find:**

- GitHub Actions workflow logs
- Slack notifications
- Deployment registry
- CloudFormation stack tags
- Monitor logs

## Deployment Registry

**Location:** `.deployment-registry/deployments.json`

**Format:**

```json
{
  "deployments": [
    {
      "correlation_id": "20260114-123456-abc123",
      "workflow_run_id": "12345",
      "environment": "production",
      "stack_name": "CourtCaseManagementStack",
      "status": "IN_PROGRESS",
      "started_at": "2026-01-14T12:34:56Z",
      "updated_at": "2026-01-14T12:44:56Z"
    }
  ]
}
```

**Cleanup:**

- Entries older than 7 days are automatically removed
- Failed deployments are kept for troubleshooting
- Registry is locked during read/write operations

## Deployment History

**Location:** `.deployment-registry/deployment-history.json`

**Format:**

```json
{
  "deployments": [
    {
      "correlation_id": "20260114-123456-abc123",
      "stack_name": "CourtCaseManagementStack",
      "duration_minutes": 25,
      "completed_at": "2026-01-14T12:59:56Z"
    }
  ],
  "resource_averages": {
    "AWS::RDS::DBInstance": 900,
    "AWS::ECS::Service": 180,
    "AWS::ElasticLoadBalancingV2::LoadBalancer": 120
  },
  "average_deployment_minutes": 25,
  "last_updated": "2026-01-14T13:00:00Z"
}
```

**Usage:**

- Estimate deployment completion time
- Track deployment performance trends
- Identify slow resources
- Optimize deployment process

## Troubleshooting

### Deployment Stuck in Queue

**Symptoms:** Deployment waiting for active deployment that doesn't exist

**Diagnosis:**

```bash
# Check active deployments
bash caseapp/scripts/deployment-coordinator.sh get_active

# Check CloudFormation stack status
AWS_PAGER="" aws cloudformation describe-stacks \
  --stack-name CourtCaseManagementStack \
  --query 'Stacks[0].StackStatus'
```

**Solution:**

```bash
# Cleanup stuck deployment
bash caseapp/scripts/deployment-coordinator.sh cleanup <correlation_id>

# Or delete stack if truly stuck
AWS_PAGER="" aws cloudformation delete-stack \
  --stack-name CourtCaseManagementStack
```

### Monitor Not Sending Updates

**Symptoms:** No Slack notifications for 10+ minutes

**Diagnosis:**

```bash
# Check if monitor is running
pgrep -f "deployment-monitor.sh"

# Check monitor logs
tail -50 deployment-monitor.log
```

**Solution:**

```bash
# Monitor recovery should restart automatically
# If not, manually restart:
nohup bash caseapp/scripts/deployment-monitor.sh \
  "<correlation_id>" "CourtCaseManagementStack" \
  "C0A9M9DPFUY" "deployment-monitor.log" \
  >> deployment-monitor.log 2>&1 &
```

### Slack Notifications Failing

**Symptoms:** Notifications not appearing in Slack

**Diagnosis:**

```bash
# Check retry queue status
bash caseapp/scripts/slack-retry-queue.sh status

# Check Slack MCP connectivity
mcp_slack_conversations_history --channel_id="C0A9M9DPFUY" --limit=1
```

**Solution:**

```bash
# Process retry queue manually
bash caseapp/scripts/slack-retry-queue.sh process

# Check dead letter queue
ls -la .slack-retry-queue/dead_letter_*
```

### Registry Unavailable

**Symptoms:** "Registry unavailable, falling back to CloudFormation-only coordination"

**Diagnosis:**

```bash
# Check registry file
ls -la .deployment-registry/deployments.json

# Check file permissions
stat .deployment-registry/deployments.json
```

**Solution:**

```bash
# Recreate registry
mkdir -p .deployment-registry
echo '{"deployments":[]}' > .deployment-registry/deployments.json
chmod 644 .deployment-registry/deployments.json
```

### Inaccurate Time Estimates

**Symptoms:** Estimated completion time is way off

**Diagnosis:**

```bash
# Check deployment history
cat .deployment-registry/deployment-history.json | jq '.average_deployment_minutes'

# Check resource averages
cat .deployment-registry/deployment-history.json | jq '.resource_averages'
```

**Solution:**

```bash
# Collect fresh historical data
bash caseapp/scripts/deployment-time-estimator.sh collect

# Verify updated averages
cat .deployment-registry/deployment-history.json | jq '.average_deployment_minutes'
```

## Best Practices

### 1. Always Use Correlation IDs

Include correlation ID in all logs, notifications, and troubleshooting:

```bash
echo "[$(date)] [$CORRELATION_ID] Starting deployment..."
```

### 2. Monitor Deployments Actively

Don't just trigger and forget:

- Check Slack notifications
- Review monitor logs
- Verify completion

### 3. Clean Up Failed Deployments

After failures, clean up resources:

```bash
# Delete failed stack
AWS_PAGER="" aws cloudformation delete-stack --stack-name CourtCaseManagementStack

# Cleanup registry
bash caseapp/scripts/deployment-coordinator.sh cleanup <correlation_id>
```

### 4. Update Deployment History

After successful deployments:

```bash
bash caseapp/scripts/deployment-time-estimator.sh update \
  "<correlation_id>" "<duration_minutes>"
```

### 5. Process Retry Queue Regularly

Set up a cron job to process failed notifications:

```bash
# Every 5 minutes
*/5 * * * * bash /path/to/slack-retry-queue.sh process
```

### 6. Review Dead Letter Queue

Check for permanently failed notifications:

```bash
# Weekly review
ls -la .slack-retry-queue/dead_letter_*
```

### 7. Collect Historical Data

After major deployments:

```bash
bash caseapp/scripts/deployment-time-estimator.sh collect
```

## Integration with GitHub Actions

The coordination system is integrated into `.github/workflows/ci-cd.yml`:

**Pre-Deployment:**

1. Generate correlation ID
2. Check if deployment can proceed
3. Wait for active deployment if needed
4. Register deployment
5. Send start notification

**During Deployment:**

1. Start monitoring in background
2. Start monitor recovery
3. Run CDK deployment
4. Monitor sends progress updates

**Post-Deployment:**

1. Send completion notification
2. Cleanup deployment registry
3. Update deployment history

**Always Runs:**

- Cleanup step (even on failure)
- Final notification

## Summary

The deployment coordination system provides:

✅ **Concurrent Deployment Prevention** - No more conflicts
✅ **Real-Time Monitoring** - Know what's happening
✅ **Automatic Error Recovery** - Self-healing system
✅ **Time Estimation** - Know when it will finish
✅ **Slack Integration** - Stay informed
✅ **Correlation IDs** - Easy troubleshooting
✅ **Historical Tracking** - Performance insights

**Key Files:**

- `deployment-coordinator.sh` - Coordination logic
- `deployment-monitor.sh` - Real-time monitoring
- `slack-notifier.sh` - Notifications
- `monitor-recovery.sh` - Error recovery
- `slack-retry-queue.sh` - Notification retry
- `registry-fallback.sh` - Fallback coordination
- `deployment-time-estimator.sh` - Time estimation

**Key Directories:**

- `.deployment-registry/` - Active deployments
- `.slack-retry-queue/` - Failed notifications

For more details, see individual script documentation and the implementation plan in `.kiro/specs/deployment-infrastructure-reliability/`.
