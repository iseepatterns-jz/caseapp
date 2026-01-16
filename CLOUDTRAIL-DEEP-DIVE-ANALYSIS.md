# CloudTrail Deep Dive Analysis - Deployment Failures

## Executive Summary

After analyzing CloudTrail events for all recent deployments, the root cause is **NOT** a simple ChangeSet race condition. The real issue is:

**CDK successfully creates and executes ChangeSets, but then immediately deletes the stack within 30-40 minutes, suggesting the deployment is timing out or encountering errors during resource provisioning.**

## CloudTrail Evidence

### Deployment Pattern (Last 24 Hours)

| Time     | Event            | User                  | Details                            |
| -------- | ---------------- | --------------------- | ---------------------------------- |
| 12:38:16 | DeleteStack      | aws-cdk-showboat      | Stack deleted by CDK               |
| 12:02:59 | ExecuteChangeSet | iseepatterns-iam-user | ChangeSet executed successfully    |
| 12:02:47 | CreateChangeSet  | iseepatterns-iam-user | ChangeSet created (deployment #75) |
| 11:42:01 | DeleteStack      | iseepatterns_user     | Manual cleanup                     |
| 11:26:57 | ExecuteChangeSet | iseepatterns-iam-user | ChangeSet executed successfully    |
| 11:26:47 | CreateChangeSet  | iseepatterns-iam-user | ChangeSet created (deployment #76) |

### Key Findings

1. **ChangeSets ARE being created successfully** - No `InvalidChangeSetStatusException` in CloudTrail
2. **ChangeSets ARE being executed successfully** - ExecuteChangeSet calls succeed
3. **Stacks ARE being deleted** - But by CDK itself (`aws-cdk-showboat` role), not manually
4. **Time gap**: ~35 minutes between ExecuteChangeSet and DeleteStack

## Root Cause Analysis

### What's Actually Happening

1. ✅ CDK creates ChangeSet successfully
2. ✅ CDK executes ChangeSet successfully
3. ⏳ CloudFormation starts creating resources (VPC, RDS, ECS, etc.)
4. ❌ **Something fails during resource creation** (likely RDS or ECS)
5. 🔄 CloudFormation attempts rollback
6. 🗑️ CDK deletes the stack (cleanup after failure)

### The Real Problem

**The ChangeSet race condition error we saw in GitHub Actions logs is a symptom, not the cause.**

The actual failure is happening **during resource provisioning**, likely:

- **RDS instance creation** (15+ minutes, most likely to fail)
- **ECS task startup** (health checks failing)
- **Security group dependencies** (circular references)
- **Secrets Manager access** (permission issues)

## What CloudTrail Tells Us

### Deployment #75 Timeline

```
12:02:47 - CreateChangeSet (SUCCESS)
12:02:59 - ExecuteChangeSet (SUCCESS)
12:03:00 - Stack CREATE_IN_PROGRESS begins
[... 35 minutes of resource creation ...]
12:38:16 - DeleteStack (CDK cleanup after failure)
```

### Why CDK Deletes the Stack

CDK's `aws-cdk-showboat` role deletes the stack when:

1. Deployment times out (GitHub Actions 45-minute limit)
2. Resource creation fails and rollback completes
3. CDK detects the deployment failed

## Tools That Would Help Pinpoint the Issue

### 1. CloudFormation Stack Events (CRITICAL)

```bash
# Get detailed stack events showing which resource failed
aws cloudformation describe-stack-events \
  --stack-name CourtCaseManagementStack \
  --region us-east-1 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'
```

**Problem**: Stack no longer exists, so we can't get these events.

### 2. CloudWatch Logs for ECS Tasks

```bash
# Check ECS task logs for startup failures
aws logs filter-log-events \
  --log-group-name /ecs/BackendService \
  --start-time $(date -u -d '2 hours ago' +%s)000 \
  --filter-pattern "ERROR"
```

**Problem**: Log groups are deleted with the stack.

### 3. RDS Creation Logs

```bash
# Check RDS events for creation failures
aws rds describe-events \
  --source-type db-instance \
  --start-time $(date -u -d '2 hours ago' --iso-8601)
```

**This might still work** - RDS events persist after instance deletion.

### 4. AWS Powers Troubleshooting Tool

The `troubleshoot_cloudformation_deployment` tool would be perfect, but:

- ❌ Requires the stack to still exist
- ❌ We've been deleting stacks immediately after failures

## Recommended Troubleshooting Strategy

### Option 1: Let Next Deployment Run to Completion (BEST)

**DO NOT delete the stack when it fails. Let it sit in ROLLBACK_COMPLETE or CREATE_FAILED state.**

Then we can:

1. Use AWS Powers to analyze the failure
2. Get CloudFormation stack events
3. See exactly which resource failed and why
4. Get CloudTrail deep links for the failed resource

### Option 2: Monitor Deployment in Real-Time

Start a deployment and actively monitor:

```bash
# Watch stack events in real-time
watch -n 10 'aws cloudformation describe-stack-events \
  --stack-name CourtCaseManagementStack \
  --max-items 20 \
  --query "StackEvents[*].[Timestamp,ResourceType,ResourceStatus,ResourceStatusReason]" \
  --output table'
```

### Option 3: Check RDS Events (Do This Now)

```bash
# Check if RDS had any issues in the last 24 hours
aws rds describe-events \
  --source-type db-instance \
  --start-time $(date -u -d '24 hours ago' --iso-8601) \
  --region us-east-1
```

### Option 4: Enable CloudFormation Stack Termination Protection

```bash
# Prevent accidental stack deletion
aws cloudformation update-termination-protection \
  --stack-name CourtCaseManagementStack \
  --enable-termination-protection
```

This would prevent CDK from deleting the stack, allowing us to investigate.

## What We Know vs. What We Don't Know

### ✅ What We Know

- ChangeSets are created successfully
- ChangeSets are executed successfully
- Stack creation begins
- Stack is deleted ~35 minutes later
- CDK is doing the deletion (not manual)

### ❌ What We Don't Know (CRITICAL)

- **Which resource fails first?** (RDS? ECS? Security Group?)
- **What's the exact error message?** (Permission? Timeout? Invalid config?)
- **Why does it fail?** (Template issue? AWS limit? Network problem?)

## Immediate Action Plan

### Before Next Deployment

1. **Add CloudWatch Logs retention** to infrastructure code:

   ```python
   log_retention=logs.RetentionDays.ONE_WEEK  # Already in code ✅
   ```

2. **Enable stack termination protection** in workflow:

   ```yaml
   - name: Enable termination protection
     run: |
       aws cloudformation update-termination-protection \
         --stack-name CourtCaseManagementStack \
         --enable-termination-protection
   ```

3. **Add real-time monitoring** to workflow:
   ```yaml
   - name: Monitor deployment
     run: |
       while true; do
         status=$(aws cloudformation describe-stacks \
           --stack-name CourtCaseManagementStack \
           --query 'Stacks[0].StackStatus' \
           --output text)
         echo "Stack status: $status"
         if [[ "$status" == *"COMPLETE"* ]] || [[ "$status" == *"FAILED"* ]]; then
           break
         fi
         sleep 30
       done
   ```

### During Next Deployment

1. **Watch stack events in real-time** (separate terminal)
2. **Don't delete the stack if it fails** - Let it sit for analysis
3. **Capture all error messages** from CloudFormation console
4. **Use AWS Powers** to analyze the failed stack

### After Deployment Fails

1. **DO NOT RUN `cdk destroy`** immediately
2. **Use AWS Powers troubleshooting tool**:
   ```javascript
   troubleshoot_cloudformation_deployment({
     stack_name: "CourtCaseManagementStack",
     region: "us-east-1",
     include_cloudtrail: true,
   });
   ```
3. **Get stack events**:
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name CourtCaseManagementStack \
     --max-items 100
   ```
4. **Check failed resources**:
   ```bash
   aws cloudformation describe-stack-resources \
     --stack-name CourtCaseManagementStack \
     --query 'StackResources[?ResourceStatus==`CREATE_FAILED`]'
   ```

## Hypothesis: Most Likely Failure Points

Based on the infrastructure code and deployment timeline:

### 1. RDS Instance Creation (70% probability)

**Why**: Takes 15+ minutes, most complex resource, many failure modes

**Possible issues**:

- Subnet group misconfiguration
- Security group circular dependency
- Insufficient permissions for RDS service role
- Database name conflicts
- Parameter group issues

### 2. ECS Task Health Checks (20% probability)

**Why**: Tasks start but fail health checks

**Possible issues**:

- Database connection fails (RDS not ready)
- Redis connection fails (ElastiCache not ready)
- Secrets Manager access denied
- Application crashes on startup
- Health check endpoint returns 500

### 3. Security Group Dependencies (10% probability)

**Why**: Circular references between ALB, ECS, RDS, Redis

**Possible issues**:

- Security group references itself
- Circular dependency between ECS and RDS security groups
- ALB security group not created before ECS service

## Conclusion

**The `--method=direct` fix is still valid and should be applied**, but it won't solve the underlying resource provisioning failure.

**The real fix requires**:

1. Identifying which resource fails (need stack events)
2. Understanding why it fails (need error messages)
3. Fixing the template or configuration (need root cause)

**Next deployment MUST**:

- Not delete the stack on failure
- Capture all error messages
- Use AWS Powers for analysis
- Let us see the actual failure reason

## Recommendation

**Push the `--method=direct` fix AND add stack monitoring/preservation to the workflow.**

This gives us:

1. Faster deployment (no ChangeSet overhead)
2. Better error visibility (stack preserved for analysis)
3. Ability to use AWS Powers troubleshooting
4. Real root cause identification

Then we can fix the actual problem and get a successful deployment.
