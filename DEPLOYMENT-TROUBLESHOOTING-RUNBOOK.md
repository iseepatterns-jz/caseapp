# Deployment Troubleshooting Runbook

## Overview

This runbook provides step-by-step procedures for resolving common deployment coordination issues.

## Quick Reference

| Issue                       | Severity | Resolution Time | Page                                 |
| --------------------------- | -------- | --------------- | ------------------------------------ |
| Deployment stuck in queue   | High     | 5 minutes       | [Link](#deployment-stuck-in-queue)   |
| Monitor not sending updates | Medium   | 2 minutes       | [Link](#monitor-not-sending-updates) |
| Slack notifications failing | Medium   | 5 minutes       | [Link](#slack-notifications-failing) |
| Registry unavailable        | Low      | 2 minutes       | [Link](#registry-unavailable)        |
| Inaccurate time estimates   | Low      | 5 minutes       | [Link](#inaccurate-time-estimates)   |
| CloudFormation stack stuck  | High     | 15 minutes      | [Link](#cloudformation-stack-stuck)  |
| ECS tasks not starting      | High     | 10 minutes      | [Link](#ecs-tasks-not-starting)      |
| RDS creation timeout        | High     | 20 minutes      | [Link](#rds-creation-timeout)        |

## Issue: Deployment Stuck in Queue

### Symptoms

- Deployment shows "waiting for active deployment"
- No active deployment visible in CloudFormation
- Deployment has been queued for 30+ minutes

### Diagnosis Steps

1. **Check active deployments:**

```bash
bash caseapp/scripts/deployment-coordinator.sh get_active
```

2. **Check CloudFormation stack status:**

```bash
AWS_PAGER="" aws cloudformation describe-stacks \
  --stack-name CourtCaseManagementStack \
  --query 'Stacks[0].StackStatus' \
  --output text
```

3. **Check deployment registry:**

```bash
cat .deployment-registry/deployments.json | jq '.deployments'
```

### Resolution

**If no active deployment exists:**

```bash
# 1. Cleanup stuck registry entry
bash caseapp/scripts/deployment-coordinator.sh cleanup <correlation_id>

# 2. Retry deployment
gh workflow run "CI/CD Pipeline" --ref main
```

**If CloudFormation stack is stuck:**

```bash
# 1. Check stack events for errors
AWS_PAGER="" aws cloudformation describe-stack-events \
  --stack-name CourtCaseManagementStack \
  --max-items 20

# 2. If truly stuck, delete stack
AWS_PAGER="" aws cloudformation delete-stack \
  --stack-name CourtCaseManagementStack

# 3. Wait for deletion (5-10 minutes)
watch -n 30 'aws cloudformation describe-stacks --stack-name CourtCaseManagementStack 2>&1 | grep -q "does not exist" && echo "DELETED" || aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --query "Stacks[0].StackStatus" --output text'

# 4. Cleanup registry
bash caseapp/scripts/deployment-coordinator.sh cleanup <correlation_id>

# 5. Retry deployment
gh workflow run "CI/CD Pipeline" --ref main
```

### Prevention

- Monitor deployments actively
- Set up alerts for deployments exceeding 40 minutes
- Clean up failed deployments immediately

---

## Issue: Monitor Not Sending Updates

### Symptoms

- No Slack notifications for 10+ minutes
- Deployment is active but no progress updates
- Monitor log file not updating

### Diagnosis Steps

1. **Check if monitor is running:**

```bash
pgrep -f "deployment-monitor.sh" || echo "Monitor not running"
```

2. **Check monitor logs:**

```bash
tail -50 deployment-monitor.log
```

3. **Check monitor recovery status:**

```bash
pgrep -f "monitor-recovery.sh" || echo "Recovery not running"
tail -20 monitor-recovery.log
```

### Resolution

**If monitor crashed:**

```bash
# 1. Check recovery log for restart attempts
tail -50 monitor-recovery.log

# 2. If recovery exceeded max restarts, manually restart
nohup bash caseapp/scripts/deployment-monitor.sh \
  "<correlation_id>" \
  "CourtCaseManagementStack" \
  "C0A9M9DPFUY" \
  "deployment-monitor.log" \
  >> deployment-monitor.log 2>&1 &

# 3. Restart recovery monitoring
bash caseapp/scripts/monitor-recovery.sh \
  "<correlation_id>" \
  "CourtCaseManagementStack" \
  "C0A9M9DPFUY" \
  "deployment-monitor.log" &
```

**If monitor is running but not updating:**

```bash
# 1. Check CloudFormation stack status
AWS_PAGER="" aws cloudformation describe-stacks \
  --stack-name CourtCaseManagementStack \
  --query 'Stacks[0].StackStatus'

# 2. Check for stack events
AWS_PAGER="" aws cloudformation describe-stack-events \
  --stack-name CourtCaseManagementStack \
  --max-items 5

# 3. If stack is progressing, monitor should catch up
# If not, restart monitor (see above)
```

### Prevention

- Always start monitor-recovery.sh alongside deployment-monitor.sh
- Set up alerts for monitor process crashes
- Review monitor logs regularly

---

## Issue: Slack Notifications Failing

### Symptoms

- Notifications not appearing in Slack
- Retry queue growing
- Dead letter queue has entries

### Diagnosis Steps

1. **Check retry queue status:**

```bash
bash caseapp/scripts/slack-retry-queue.sh status
```

2. **Check Slack MCP connectivity:**

```bash
mcp_slack_conversations_history \
  --channel_id="C0A9M9DPFUY" \
  --limit=1
```

3. **Check dead letter queue:**

```bash
ls -la .slack-retry-queue/dead_letter_*
```

### Resolution

**If Slack MCP is down:**

```bash
# 1. Wait for Slack to recover (usually temporary)
# 2. Process retry queue once recovered
bash caseapp/scripts/slack-retry-queue.sh process

# 3. Verify notifications sent
bash caseapp/scripts/slack-retry-queue.sh status
```

**If MCP configuration issue:**

```bash
# 1. Check MCP configuration
cat ~/.kiro/settings/mcp.json | jq '.mcpServers.slack'

# 2. Test Slack MCP
mcp_slack_conversations_add_message \
  --channel_id="C0A9M9DPFUY" \
  --payload="Test message"

# 3. If fails, check Slack token
# 4. Restart Kiro to reload MCP configuration
```

**If dead letter queue has entries:**

```bash
# 1. Review failed notifications
for file in .slack-retry-queue/dead_letter_*.json; do
  echo "=== $file ==="
  cat "$file" | jq '.'
done

# 2. Manually send critical notifications
# 3. Clean up dead letter queue
rm .slack-retry-queue/dead_letter_*.json
```

### Prevention

- Set up cron job to process retry queue every 5 minutes
- Monitor dead letter queue weekly
- Test Slack MCP connectivity regularly

---

## Issue: Registry Unavailable

### Symptoms

- Warning: "Registry unavailable, falling back to CloudFormation-only coordination"
- Registry file missing or unreadable
- File permission errors

### Diagnosis Steps

1. **Check registry file exists:**

```bash
ls -la .deployment-registry/deployments.json
```

2. **Check file permissions:**

```bash
stat .deployment-registry/deployments.json
```

3. **Check file content:**

```bash
cat .deployment-registry/deployments.json | jq '.'
```

### Resolution

**If file missing:**

```bash
# 1. Recreate registry directory
mkdir -p .deployment-registry

# 2. Initialize registry file
echo '{"deployments":[]}' > .deployment-registry/deployments.json

# 3. Set permissions
chmod 644 .deployment-registry/deployments.json

# 4. Verify
cat .deployment-registry/deployments.json | jq '.'
```

**If file corrupted:**

```bash
# 1. Backup corrupted file
cp .deployment-registry/deployments.json \
   .deployment-registry/deployments.json.corrupted

# 2. Reinitialize
echo '{"deployments":[]}' > .deployment-registry/deployments.json

# 3. Manually add active deployments if known
# (Check CloudFormation for active stacks)
```

**If permission issue:**

```bash
# 1. Fix permissions
chmod 644 .deployment-registry/deployments.json
chmod 755 .deployment-registry

# 2. Verify access
cat .deployment-registry/deployments.json | jq '.'
```

### Prevention

- Include .deployment-registry in backups
- Monitor file permissions
- Use fallback mode gracefully (already implemented)

---

## Issue: Inaccurate Time Estimates

### Symptoms

- Estimated completion time is way off (±50%)
- Estimates don't improve as deployment progresses
- Historical data is missing or outdated

### Diagnosis Steps

1. **Check deployment history:**

```bash
cat .deployment-registry/deployment-history.json | jq '.average_deployment_minutes'
```

2. **Check resource averages:**

```bash
cat .deployment-registry/deployment-history.json | jq '.resource_averages'
```

3. **Check number of historical deployments:**

```bash
cat .deployment-registry/deployment-history.json | jq '.deployments | length'
```

### Resolution

**If no historical data:**

```bash
# 1. Collect historical data from CloudFormation
bash caseapp/scripts/deployment-time-estimator.sh collect

# 2. Verify data collected
cat .deployment-registry/deployment-history.json | jq '.deployments | length'

# 3. Check updated average
cat .deployment-registry/deployment-history.json | jq '.average_deployment_minutes'
```

**If historical data is outdated:**

```bash
# 1. Collect fresh data
bash caseapp/scripts/deployment-time-estimator.sh collect

# 2. Update with recent deployments
# (This happens automatically after each deployment)
```

**If estimates still inaccurate:**

```bash
# 1. Manually adjust resource averages
# Edit .deployment-registry/deployment-history.json
# Update resource_averages based on observed times

# 2. Or reset and recollect
rm .deployment-registry/deployment-history.json
bash caseapp/scripts/deployment-time-estimator.sh collect
```

### Prevention

- Collect historical data after major infrastructure changes
- Update deployment history after each deployment
- Review estimates periodically for accuracy

---

## Issue: CloudFormation Stack Stuck

### Symptoms

- Stack status shows CREATE_IN_PROGRESS for 40+ minutes
- No new stack events for 15+ minutes
- Specific resource stuck (e.g., RDS, ECS)

### Diagnosis Steps

1. **Check stack status:**

```bash
AWS_PAGER="" aws cloudformation describe-stacks \
  --stack-name CourtCaseManagementStack \
  --query 'Stacks[0].StackStatus'
```

2. **Check recent stack events:**

```bash
AWS_PAGER="" aws cloudformation describe-stack-events \
  --stack-name CourtCaseManagementStack \
  --max-items 20 \
  --query 'StackEvents[].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus,Reason:ResourceStatusReason}' \
  --output table
```

3. **Identify stuck resource:**

```bash
AWS_PAGER="" aws cloudformation describe-stack-resources \
  --stack-name CourtCaseManagementStack \
  --query 'StackResources[?ResourceStatus==`CREATE_IN_PROGRESS`]'
```

### Resolution

**If RDS is stuck:**

See [RDS Creation Timeout](#rds-creation-timeout)

**If ECS is stuck:**

See [ECS Tasks Not Starting](#ecs-tasks-not-starting)

**If other resource stuck:**

```bash
# 1. Wait 10 more minutes (some resources are slow)

# 2. If still stuck, cancel deployment
# (CloudFormation will attempt rollback)

# 3. If rollback fails, manually delete stuck resources
# Then delete stack

# 4. Clean up and retry
bash caseapp/scripts/deployment-coordinator.sh cleanup <correlation_id>
gh workflow run "CI/CD Pipeline" --ref main
```

### Prevention

- Set realistic timeout values in CDK
- Monitor resource creation actively
- Use pre-deployment tests to catch issues early

---

## Issue: ECS Tasks Not Starting

### Symptoms

- ECS service created but no tasks running
- Tasks start then immediately stop
- Task stopped reason shows errors

### Diagnosis Steps

1. **Check ECS service status:**

```bash
AWS_PAGER="" aws ecs describe-services \
  --cluster CourtCaseCluster \
  --services CourtCaseBackendService \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Events:events[0:3]}'
```

2. **List tasks:**

```bash
AWS_PAGER="" aws ecs list-tasks \
  --cluster CourtCaseCluster \
  --service-name CourtCaseBackendService
```

3. **Check stopped tasks:**

```bash
AWS_PAGER="" aws ecs list-tasks \
  --cluster CourtCaseCluster \
  --desired-status STOPPED \
  --max-items 5
```

4. **Get stopped task details:**

```bash
TASK_ARN=$(aws ecs list-tasks --cluster CourtCaseCluster --desired-status STOPPED --max-items 1 --query 'taskArns[0]' --output text)

AWS_PAGER="" aws ecs describe-tasks \
  --cluster CourtCaseCluster \
  --tasks "$TASK_ARN" \
  --query 'tasks[0].{StoppedReason:stoppedReason,Containers:containers[].{Name:name,Reason:reason,ExitCode:exitCode}}'
```

### Resolution

**If secret not found:**

```bash
# 1. Check if secret exists
AWS_PAGER="" aws secretsmanager list-secrets \
  --query 'SecretList[?contains(Name, `courtcase`)].Name'

# 2. Create missing secret
aws secretsmanager create-secret \
  --name courtcase-database-credentials \
  --secret-string '{"username":"admin","password":"<secure-password>"}'

# 3. Update ECS service to force new deployment
AWS_PAGER="" aws ecs update-service \
  --cluster CourtCaseCluster \
  --service CourtCaseBackendService \
  --force-new-deployment
```

**If health check failing:**

```bash
# 1. Check task logs
AWS_PAGER="" aws logs get-log-events \
  --log-group-name /ecs/courtcase-backend \
  --log-stream-name <stream-name> \
  --limit 50

# 2. Check application health endpoint
# (Once task is running)
curl -f http://<task-ip>:8000/health

# 3. Fix health check configuration in CDK
# 4. Redeploy
```

**If insufficient resources:**

```bash
# 1. Check cluster capacity
AWS_PAGER="" aws ecs describe-clusters \
  --clusters CourtCaseCluster \
  --query 'clusters[0].{RegisteredInstances:registeredContainerInstancesCount,RunningTasks:runningTasksCount,PendingTasks:pendingTasksCount}'

# 2. If using Fargate, check service quotas
AWS_PAGER="" aws service-quotas get-service-quota \
  --service-code fargate \
  --quota-code L-3032A538

# 3. Request quota increase if needed
```

### Prevention

- Test Docker images locally before deploying
- Verify secrets exist before deployment
- Use pre-deployment test suite
- Monitor ECS task startup immediately after deployment

---

## Issue: RDS Creation Timeout

### Symptoms

- RDS instance stuck in "creating" state for 20+ minutes
- CloudFormation stack waiting on RDS resource
- No errors but no progress

### Diagnosis Steps

1. **Check RDS instance status:**

```bash
AWS_PAGER="" aws rds describe-db-instances \
  --query 'DBInstances[?contains(DBInstanceIdentifier, `courtcase`)].{ID:DBInstanceIdentifier,Status:DBInstanceStatus,Created:InstanceCreateTime}' \
  --output table
```

2. **Check RDS events:**

```bash
AWS_PAGER="" aws rds describe-events \
  --source-type db-instance \
  --duration 60 \
  --max-records 20
```

3. **Check subnet group:**

```bash
AWS_PAGER="" aws rds describe-db-subnet-groups \
  --query 'DBSubnetGroups[?contains(DBSubnetGroupName, `courtcase`)]'
```

### Resolution

**If RDS is still creating (normal):**

```bash
# 1. Wait - RDS creation takes 15-20 minutes normally
# 2. Monitor progress
watch -n 60 'aws rds describe-db-instances --query "DBInstances[?contains(DBInstanceIdentifier, \`courtcase\`)].{ID:DBInstanceIdentifier,Status:DBInstanceStatus}" --output table'

# 3. Check for completion
# Status should change to "available"
```

**If RDS creation failed:**

```bash
# 1. Check RDS events for error
AWS_PAGER="" aws rds describe-events \
  --source-type db-instance \
  --duration 60

# 2. Common issues:
#    - Insufficient subnet IPs
#    - Security group misconfiguration
#    - Invalid parameter group

# 3. Fix issue in CDK
# 4. Delete failed instance
AWS_PAGER="" aws rds delete-db-instance \
  --db-instance-identifier <instance-id> \
  --skip-final-snapshot

# 5. Redeploy
```

**If RDS stuck (rare):**

```bash
# 1. Contact AWS Support
# 2. Provide instance ID and creation time
# 3. While waiting, consider:
#    - Canceling deployment
#    - Deleting stuck instance
#    - Redeploying to different AZ
```

### Prevention

- Ensure sufficient IP addresses in subnets
- Validate security group rules
- Use smaller instance types for faster creation
- Test RDS configuration in staging first

---

## Emergency Procedures

### Complete System Reset

If everything is broken and you need to start fresh:

```bash
# 1. Stop all monitoring processes
pkill -f "deployment-monitor.sh"
pkill -f "monitor-recovery.sh"

# 2. Delete CloudFormation stack
AWS_PAGER="" aws cloudformation delete-stack \
  --stack-name CourtCaseManagementStack

# 3. Wait for deletion
watch -n 30 'aws cloudformation describe-stacks --stack-name CourtCaseManagementStack 2>&1 | grep -q "does not exist" && echo "DELETED" || aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --query "Stacks[0].StackStatus" --output text'

# 4. Clean up orphaned resources
bash verify-resources-before-deploy.sh

# 5. Reset deployment registry
rm -rf .deployment-registry
mkdir -p .deployment-registry
echo '{"deployments":[]}' > .deployment-registry/deployments.json

# 6. Reset retry queue
rm -rf .slack-retry-queue

# 7. Run pre-deployment tests
bash caseapp/scripts/pre-deployment-test-suite.sh

# 8. Deploy fresh
gh workflow run "CI/CD Pipeline" --ref main
```

### Rollback Deployment

If deployment succeeded but application is broken:

```bash
# 1. Identify last known good deployment
cat .deployment-registry/deployment-history.json | jq '.deployments[-5:]'

# 2. Get commit hash for that deployment
gh run view <workflow-run-id>

# 3. Revert to that commit
git revert <commit-hash>
git push origin main

# 4. Deploy reverted version
gh workflow run "CI/CD Pipeline" --ref main
```

## Escalation

### When to Escalate

Escalate to senior engineer or AWS Support if:

- Issue persists after following runbook
- Data loss risk
- Production outage > 1 hour
- AWS service issue suspected
- Security incident

### Escalation Information to Provide

1. **Correlation ID** - For tracing
2. **Timeline** - When issue started
3. **Steps Taken** - What you've tried
4. **Current State** - What's broken now
5. **Logs** - Relevant log excerpts
6. **Stack Events** - CloudFormation events
7. **Error Messages** - Exact error text

### Contact Information

- **AWS Support:** [AWS Support Center](https://console.aws.amazon.com/support/)
- **Slack:** #kiro-updates, #kiro-interact
- **GitHub Issues:** [Repository Issues](https://github.com/owner/repo/issues)

## Summary

This runbook covers the most common deployment coordination issues. For additional help:

- Review `DEPLOYMENT-COORDINATION-GUIDE.md` for system overview
- Check individual script documentation
- Review `.kiro/specs/deployment-infrastructure-reliability/` for design details
- Use pre-deployment test suite to prevent issues

**Remember:** Most issues can be resolved by:

1. Checking logs
2. Verifying AWS resource status
3. Cleaning up stuck resources
4. Retrying deployment

When in doubt, use the emergency reset procedure and start fresh.
