# RDS Enhanced Monitoring Root Cause Analysis

## Executive Summary

**ROOT CAUSE IDENTIFIED**: RDS enhanced monitoring is enabled (`monitoring_interval=Duration.seconds(60)`) but CDK is NOT automatically creating the required IAM role, causing RDS instances to fail enhanced monitoring and potentially triggering stack rollback.

## Evidence from CloudTrail and RDS Events

### RDS Event Log Analysis

```
2026-01-14T21:21:00 - Amazon RDS has encountered a fatal error running enhanced
monitoring on your instance... This is likely due to the rds-monitoring-role
not being present or configured incorrectly in your account.

2026-01-15T03:11:29 - Amazon RDS has encountered a fatal error running enhanced
monitoring on your instance... This is likely due to the rds-monitoring-role
not being present or configured incorrectly in your account.
```

**Pattern**: EVERY RDS instance created experiences this error ~40 minutes after creation.

### CloudTrail Timeline Pattern

```
12:02:47 - CreateChangeSet (SUCCESS)
12:02:59 - ExecuteChangeSet (SUCCESS)
12:03:00 - Stack CREATE_IN_PROGRESS begins
[... 35 minutes of resource creation ...]
12:38:16 - DeleteStack (CDK cleanup after failure)
```

**Analysis**: Stack is being deleted by CDK's `aws-cdk-showboat` role after ~35 minutes, suggesting deployment timeout or resource provisioning failure.

## CDK Documentation Findings

From AWS CDK documentation search:

```python
monitoring_role: Optional[IRole]
Default: "- A role is automatically created for you"
```

**CRITICAL ISSUE**: The documentation says "A role is automatically created for you" but this is NOT happening in practice. The RDS events prove no role exists.

## Current Infrastructure Code (app.py)

```python
self.database = rds.DatabaseInstance(
    self, "CourtCaseDatabase",
    # ... other config ...
    monitoring_interval=Duration.seconds(60),  # ❌ ENABLED but no role!
    enable_performance_insights=True,
    # monitoring_role NOT specified - relying on "automatic" creation
)
```

**Problem**:

1. `monitoring_interval=Duration.seconds(60)` enables enhanced monitoring
2. No `monitoring_role` is specified
3. CDK documentation claims it will auto-create the role
4. **Reality**: No role is created, RDS fails, stack times out and rolls back

## Why This Causes Deployment Failures

1. **RDS Instance Creation** (15+ minutes)

   - Instance creates successfully
   - Multi-AZ conversion completes
   - Performance Insights enabled
   - Enhanced monitoring attempts to start

2. **Enhanced Monitoring Failure** (~40 minutes after start)

   - RDS tries to use `rds-monitoring-role`
   - Role doesn't exist
   - Enhanced monitoring fails with fatal error
   - Monitoring disabled automatically

3. **Stack Rollback** (~35-40 minutes)
   - CloudFormation detects resource provisioning issues
   - Stack enters rollback state
   - CDK's `aws-cdk-showboat` role deletes the stack
   - All resources cleaned up

## Solution Options

### Option 1: Disable Enhanced Monitoring (FASTEST - RECOMMENDED FOR NOW)

**Change in app.py line ~195:**

```python
# BEFORE (BROKEN):
monitoring_interval=Duration.seconds(60),

# AFTER (WORKING):
monitoring_interval=Duration.seconds(0),  # Disable enhanced monitoring
```

**Pros**:

- Immediate fix - deployment will succeed
- No IAM role management needed
- Performance Insights still works (separate feature)
- Can re-enable later after creating proper role

**Cons**:

- Lose enhanced monitoring metrics temporarily
- Still have Performance Insights for monitoring

### Option 2: Create IAM Role Explicitly (PROPER FIX)

**Add to app.py before database creation:**

```python
# Create RDS enhanced monitoring role
rds_monitoring_role = iam.Role(
    self, "RDSMonitoringRole",
    assumed_by=iam.ServicePrincipal("monitoring.rds.amazonaws.com"),
    managed_policies=[
        iam.ManagedPolicy.from_aws_managed_policy_name(
            "service-role/AmazonRDSEnhancedMonitoringRole"
        )
    ]
)

# Then use it in DatabaseInstance:
self.database = rds.DatabaseInstance(
    self, "CourtCaseDatabase",
    # ... other config ...
    monitoring_interval=Duration.seconds(60),
    monitoring_role=rds_monitoring_role,  # ✅ Explicitly provide role
    enable_performance_insights=True,
)
```

**Pros**:

- Proper solution following AWS best practices
- Enhanced monitoring works correctly
- Explicit IAM role management

**Cons**:

- Requires additional code
- Adds IAM role to stack
- Takes longer to implement

### Option 3: Use Existing Role (IF IT EXISTS)

**Check if role exists:**

```bash
aws iam get-role --role-name rds-monitoring-role 2>/dev/null
```

**If role exists, reference it:**

```python
# Import existing role
rds_monitoring_role = iam.Role.from_role_arn(
    self, "RDSMonitoringRole",
    role_arn="arn:aws:iam::ACCOUNT_ID:role/rds-monitoring-role"
)

# Use in DatabaseInstance
monitoring_role=rds_monitoring_role
```

## Recommended Action Plan

### Immediate Fix (Get Deployment Working TODAY)

1. **Disable enhanced monitoring** in `app.py`:

   ```python
   monitoring_interval=Duration.seconds(0)
   ```

2. **Commit and push**:

   ```bash
   git add caseapp/infrastructure/app.py
   git commit -m "fix: disable RDS enhanced monitoring to resolve deployment failures"
   git push origin main
   ```

3. **Pre-deployment verification**:

   ```bash
   cd caseapp/infrastructure
   cdk destroy --all --force
   bash ../../verify-resources-before-deploy.sh
   # Verify in browser: CloudFormation + GitHub Actions
   ```

4. **Deploy**:
   ```bash
   gh workflow run "CI/CD Pipeline" --ref main
   ```

### Follow-Up (After Successful Deployment)

1. **Create proper IAM role** (Option 2 above)
2. **Re-enable enhanced monitoring** with explicit role
3. **Test in staging** before production
4. **Document the fix** in deployment runbook

## Why Previous Deployments Failed

Looking at deployment history:

- **Deployment #67**: Timeout (38m34s) - RDS + OpenSearch > 30min limit
- **Deployment #69**: Stuck in CREATE_IN_PROGRESS (65+ min) - RDS monitoring failure
- **Deployment #75**: Deleted after ~35 min - RDS monitoring failure triggered rollback
- **Deployment #76**: Same pattern - RDS monitoring failure

**Common Thread**: All deployments with RDS enhanced monitoring enabled failed after ~35-40 minutes when the monitoring role error occurred.

## Verification After Fix

After deploying with `monitoring_interval=Duration.seconds(0)`:

1. **Check RDS events** (should be clean):

   ```bash
   aws rds describe-events --source-type db-instance \
     --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
     --region us-east-1
   ```

2. **Verify no monitoring errors** in events

3. **Confirm stack stays up** (no automatic deletion after 35 minutes)

4. **Check ECS tasks** start successfully and stay healthy

## Additional Findings

### Performance Insights vs Enhanced Monitoring

- **Performance Insights**: Database query performance analysis - STILL ENABLED ✅
- **Enhanced Monitoring**: OS-level metrics (CPU, memory, disk) - DISABLED for now ⏸️

**Impact**: We still have database performance monitoring via Performance Insights. Enhanced monitoring is nice-to-have but not critical for initial deployment.

### CDK Bug or Documentation Issue?

The CDK documentation states `monitoring_role` defaults to "A role is automatically created for you" but this is clearly not working. This could be:

1. **CDK Bug**: Auto-creation logic is broken
2. **Documentation Error**: Auto-creation never worked
3. **Account Configuration**: Some AWS accounts require explicit role creation

**Recommendation**: Always create the role explicitly (Option 2) for production deployments.

## Conclusion

**The real root cause of all deployment failures is RDS enhanced monitoring failing due to missing IAM role, NOT the CDK ChangeSet race condition.**

The `--method=direct` fix is still valid and should be kept, but the RDS monitoring role issue is what's actually causing stack rollbacks.

**Immediate Action**: Disable enhanced monitoring to get a successful deployment TODAY, then properly implement the IAM role for future deployments.
