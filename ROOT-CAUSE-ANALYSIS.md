# Root Cause Analysis: CloudFormation Deployment Failures

## Executive Summary

**Root Cause**: The pre-deployment validation script (`enhanced-deployment-validation.sh`) is interfering with active CloudFormation deployments by attempting to clean up orphaned resources while a deployment is in progress.

**Impact**: Deployments fail in a repeating cycle, entering DELETE_FAILED state due to RDS deletion timeouts.

**Solution**: Modify validation script to detect active deployments and wait for resource cleanup to complete before starting new deployments.

---

## Timeline of Failure

### Deployment Attempt (2026-01-13)

| Time (UTC) | Event                                 | Details                                                                  |
| ---------- | ------------------------------------- | ------------------------------------------------------------------------ |
| 23:49:06   | Stack creation starts                 | CloudFormation begins creating resources                                 |
| 23:50:59   | GitHub Actions workflow starts        | CI/CD pipeline triggered                                                 |
| 23:53:38   | RDS instance created                  | Database instance successfully created                                   |
| 00:07:32   | **Validation script interferes**      | Script detects old RDS instance and tries to disable deletion protection |
| 00:07:46   | DELETE initiated                      | CloudFormation receives "User Initiated" delete (18 minutes after start) |
| 00:10:18   | DB Subnet Group DELETE_FAILED         | Cannot delete because RDS instance still using it                        |
| 00:25:36   | Database Security Group DELETE_FAILED | Has dependent objects (network interfaces)                               |
| 00:41:29   | Database Subnets DELETE_FAILED        | Have dependencies and cannot be deleted                                  |
| 00:43:51   | Stack enters DELETE_FAILED            | Multiple resources failed to delete                                      |

---

## Root Cause Details

### The Problem

The `enhanced-deployment-validation.sh` script has the following logic:

1. Check for existing CloudFormation stack
2. If stack exists with DELETE_FAILED status, attempt cleanup
3. Check for RDS instances with deletion protection
4. **Disable deletion protection on found RDS instances**
5. Attempt to delete the stack

### Why This Causes Failures

**Scenario 1: Orphaned Resources from Previous Deployment**

- Previous deployment fails and leaves RDS instance
- New deployment starts
- Validation script finds the old RDS instance
- Script tries to clean it up WHILE new deployment is creating resources
- CloudFormation gets confused about which resources belong to which operation
- Triggers rollback

**Scenario 2: Race Condition**

- Deployment creates RDS instance (takes 4-5 minutes)
- Validation script runs in parallel or shortly after
- Script sees RDS instance and thinks it's orphaned
- Attempts to disable deletion protection
- CloudFormation interprets this as a conflict and rolls back

### Evidence from Logs

```
2026-01-14T00:07:32 [INFO] Modifying RDS instance to disable deletion protection...
2026-01-14T00:07:33 "DBInstanceIdentifier": "courtcasemanagementstack-courtcasedatabasef7bbe8d0-rmc3vwwjyqcq"
2026-01-14T00:07:33 "DBInstanceStatus": "available"
2026-01-14T00:07:33 "InstanceCreateTime": "2026-01-13T23:53:38.911000+00:00"
```

The validation script modified an RDS instance that was created just 14 minutes earlier, triggering the cascade of failures.

---

## Why Deployments Keep Failing

### The Cycle

```
1. Deployment starts
   ↓
2. Creates VPC, subnets, security groups, RDS
   ↓
3. Validation script detects "orphaned" RDS
   ↓
4. Script tries to clean up RDS
   ↓
5. CloudFormation gets confused
   ↓
6. Initiates rollback/delete
   ↓
7. RDS takes 10-15 minutes to delete
   ↓
8. Other resources can't delete (dependencies)
   ↓
9. Stack enters DELETE_FAILED
   ↓
10. Next deployment starts
    ↓
    [REPEAT FROM STEP 1]
```

### Dependency Chain

When CloudFormation tries to delete resources, it must follow this order:

1. **ECS Service** (depends on RDS, security groups)
2. **RDS Instance** (10-15 minutes to delete)
3. **DB Subnet Group** (depends on RDS being deleted)
4. **Database Security Group** (depends on network interfaces being detached)
5. **Database Subnets** (depend on subnet group being deleted)
6. **VPC** (depends on all subnets being deleted)

If RDS deletion takes too long, the entire chain fails.

---

## Configuration Analysis

### GitHub Actions Timeouts

From `.github/workflows/ci-cd.yml`:

```yaml
jobs:
  deploy-production:
    timeout-minutes: 120 # 2 hours for entire job

    steps:
      - name: Run comprehensive pre-deployment validation
        timeout-minutes: 35 # Validation step timeout

      - name: Deploy to production
        timeout-minutes: 90 # Deployment step timeout
```

**Analysis**: The timeouts are generous (120 minutes total), so timeout is NOT the root cause.

### CDK Configuration

From `caseapp/infrastructure/app.py`:

```python
self.database = rds.DatabaseInstance(
    self, "CourtCaseDatabase",
    deletion_protection=True,  # Requires manual disable before delete
    removal_policy=RemovalPolicy.RETAIN,  # Prevents accidental deletion
    multi_az=True,  # High availability (slower to create/delete)
)
```

**Analysis**:

- `deletion_protection=True` is correct for production
- `multi_az=True` means RDS takes longer to create and delete
- These settings are appropriate but contribute to slow deletion times

### Validation Script Logic

From `caseapp/scripts/enhanced-deployment-validation.sh`:

```bash
# Check for RDS instances with deletion protection
if [ -n "$rds_instances" ]; then
    log_warning "Found RDS instances with deletion protection"

    # Disable deletion protection
    aws rds modify-db-instance \
        --db-instance-identifier "$instance" \
        --no-deletion-protection
fi
```

**Problem**: This runs BEFORE checking if a deployment is in progress!

---

## The Fix

### Required Changes

1. **Check for Active Deployments First**

   ```bash
   # Before any cleanup, check if deployment is in progress
   stack_status=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].StackStatus' --output text)

   if [[ "$stack_status" =~ (CREATE_IN_PROGRESS|UPDATE_IN_PROGRESS|ROLLBACK_IN_PROGRESS) ]]; then
       log_error "Deployment already in progress. Cannot run validation."
       exit 1
   fi
   ```

2. **Wait for RDS Deletion to Complete**

   ```bash
   # If RDS is deleting, wait for it to complete
   if [ "$rds_status" = "deleting" ]; then
       log_info "Waiting for RDS deletion to complete..."
       aws rds wait db-instance-deleted --db-instance-identifier "$instance"
   fi
   ```

3. **Add Deployment Lock Mechanism**

   ```bash
   # Create a lock file to prevent concurrent deployments
   LOCK_FILE="/tmp/deployment.lock"

   if [ -f "$LOCK_FILE" ]; then
       log_error "Another deployment is in progress"
       exit 1
   fi

   touch "$LOCK_FILE"
   trap "rm -f $LOCK_FILE" EXIT
   ```

4. **Separate Cleanup from Validation**
   - Validation should only CHECK for issues
   - Cleanup should be a separate, explicit step
   - Never clean up during active deployments

---

## Testing Strategy

### Test 1: Detect Active Deployment

```bash
# Start a deployment
cdk deploy &

# Try to run validation while deployment is active
./scripts/enhanced-deployment-validation.sh

# Expected: Script should detect active deployment and exit
```

### Test 2: Wait for RDS Deletion

```bash
# Create RDS instance
# Initiate deletion
# Run validation script

# Expected: Script should wait for RDS deletion to complete
```

### Test 3: Prevent Concurrent Deployments

```bash
# Start deployment 1
./scripts/deploy-with-validation.sh &

# Try to start deployment 2
./scripts/deploy-with-validation.sh

# Expected: Second deployment should be blocked
```

---

## Recommended Actions

### Immediate (Fix the Script)

1. ✅ Modify `enhanced-deployment-validation.sh` to check for active deployments
2. ✅ Add RDS deletion wait logic
3. ✅ Implement deployment lock mechanism
4. ✅ Test locally before pushing

### Short-term (Improve Reliability)

1. Separate validation from cleanup
2. Add deployment state tracking
3. Implement proper retry logic with backoff
4. Add deployment monitoring dashboard

### Long-term (Prevent Future Issues)

1. Use CDK deployment guards
2. Implement blue-green deployments
3. Add automated rollback on failure
4. Create deployment health checks

---

## Lessons Learned

1. **Validation scripts should never modify resources** - They should only check and report
2. **Always check for active operations** before attempting cleanup
3. **RDS deletion takes time** - Plan for 10-15 minute deletion windows
4. **Dependency chains matter** - Understand resource dependencies before cleanup
5. **Test locally first** - Catch issues before they hit CI/CD

---

## Next Steps

1. Wait for current RDS instance to finish deleting (~10 more minutes)
2. Clean up the DELETE_FAILED stack
3. Implement the fix in `enhanced-deployment-validation.sh`
4. Test the fix locally
5. Push the fix and monitor the next deployment
6. Document the fix and update runbooks

---

## Appendix: CloudFormation Events

### Failed Resources

| Resource                    | Type                    | Status        | Reason                      |
| --------------------------- | ----------------------- | ------------- | --------------------------- |
| CourtCaseVPCDatabaseSubnet1 | AWS::EC2::Subnet        | DELETE_FAILED | Has dependencies            |
| CourtCaseVPCDatabaseSubnet2 | AWS::EC2::Subnet        | DELETE_FAILED | Has dependencies            |
| ECSServiceSecurityGroup     | AWS::EC2::SecurityGroup | DELETE_FAILED | Has dependent object        |
| DatabaseSecurityGroup       | AWS::EC2::SecurityGroup | DELETE_FAILED | Has dependent object        |
| DatabaseSubnetGroup         | AWS::RDS::DBSubnetGroup | DELETE_FAILED | RDS instance still using it |

### Dependency Graph

```
VPC
├── Public Subnets
├── Private Subnets
└── Database Subnets
    ├── DB Subnet Group
    │   └── RDS Instance (10-15 min to delete)
    └── Database Security Group
        └── Network Interfaces (attached to RDS)
```

---

**Document Created**: 2026-01-14 01:15 UTC
**Status**: Root cause identified, fix pending implementation
**Priority**: HIGH - Blocking all deployments
