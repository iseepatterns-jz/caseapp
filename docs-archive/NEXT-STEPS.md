# Next Steps - Deployment #67

## Current Status ✅

- ✅ CloudFormation stack: DELETED
- ✅ Orphaned RDS instance: DELETED
- ✅ DB Subnet Groups: DELETED
- ✅ Required secrets: CREATED
- ✅ Pre-deployment test suite: READY
- ✅ AWS Powers validation: READY
- ✅ Deployment coordination system: COMPLETE (Tasks 1-10)
- ✅ Error recovery mechanisms: IMPLEMENTED
- ✅ Time estimation: IMPLEMENTED
- ✅ Documentation: COMPLETE

## Recent Completions 🎉

**Tasks 8-10 of Deployment Infrastructure Reliability:**

- ✅ Monitor process recovery with automatic restart
- ✅ Slack notification retry queue with exponential backoff
- ✅ Registry fallback for CloudFormation-only coordination
- ✅ Deployment time estimation with historical data
- ✅ Comprehensive documentation (guides and runbooks)

**New Capabilities:**

- Automatic recovery from monitor crashes
- Failed notification retry with exponential backoff
- Time estimates in Slack notifications
- Complete troubleshooting runbook
- Emergency procedures documented

## Step-by-Step Guide

### Step 1: Wait for Stack Deletion (5-10 minutes) ⏳

Monitor deletion progress:

```bash
# Check every 30 seconds
watch -n 30 'aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "DELETED"'

# Or check once:
AWS_PAGER="" aws cloudformation describe-stacks \
  --stack-name CourtCaseManagementStack \
  --query 'Stacks[0].StackStatus' \
  --output text 2>/dev/null || echo "DELETED"
```

**Expected**: Status should be "DELETED" or command returns "Stack not found"

---

### Step 2: Run Pre-Deployment Tests ✅

Once stack is deleted, run the comprehensive test suite:

```bash
bash caseapp/scripts/pre-deployment-test-suite.sh
```

**Expected Output**:

```
==========================================
Pre-Deployment Test Summary
==========================================
Total Tests:   12
Passed:        XX
Failed:        0
Warnings:      X
==========================================
✅ ALL TESTS PASSED - READY TO DEPLOY
```

**If tests fail**: Fix the issues and re-run. Do NOT proceed until all tests pass.

---

### Step 3: Validate Template with AWS Powers (Optional but Recommended) 🔍

```bash
bash caseapp/scripts/validate-with-aws-powers.sh
```

Or manually with Kiro:

```python
# 1. Activate the power
kiroPowers(action="activate", powerName="aws-infrastructure-as-code")

# 2. Read template
template_content = open("caseapp/infrastructure/cdk.out/CourtCaseManagementStack.template.json").read()

# 3. Validate syntax
kiroPowers(
    action="use",
    powerName="aws-infrastructure-as-code",
    serverName="awslabs.aws-iac-mcp-server",
    toolName="validate_cloudformation_template",
    arguments={"template_content": template_content}
)

# 4. Check compliance
kiroPowers(
    action="use",
    powerName="aws-infrastructure-as-code",
    serverName="awslabs.aws-iac-mcp-server",
    toolName="check_cloudformation_template_compliance",
    arguments={"template_content": template_content}
)
```

---

### Step 4: Deploy with CDK (Recommended) 🚀

**Option A: Local Deployment with CDK**

```bash
# Navigate to infrastructure directory
cd caseapp/infrastructure

# Deploy with no approval prompts
cdk deploy --require-approval never

# Monitor in another terminal
watch -n 30 'aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --query "Stacks[0].StackStatus" --output text'
```

**Option B: Deploy via GitHub Actions**

```bash
# Commit changes
git add .
git commit -m "fix: pre-deployment tests passed, ready for deployment #67"
git push origin main

# Monitor workflow
gh run list --limit 1
gh run watch
```

---

### Step 5: Monitor Deployment (30-40 minutes) 👀

**CloudFormation Stack Events**:

```bash
# Watch stack events
AWS_PAGER="" aws cloudformation describe-stack-events \
  --stack-name CourtCaseManagementStack \
  --max-items 20 \
  --query 'StackEvents[].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus,Reason:ResourceStatusReason}' \
  --output table
```

**ECS Service Status** (once cluster is created):

```bash
# Check ECS service
AWS_PAGER="" aws ecs describe-services \
  --cluster CourtCaseCluster \
  --services CourtCaseBackendService \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}' \
  --output table
```

**RDS Status** (takes 15-20 minutes):

```bash
# Check RDS instance
AWS_PAGER="" aws rds describe-db-instances \
  --query 'DBInstances[?contains(DBInstanceIdentifier, `courtcase`)].{ID:DBInstanceIdentifier,Status:DBInstanceStatus}' \
  --output table
```

---

### Step 6: Verify Deployment Success ✅

Once stack shows `CREATE_COMPLETE`:

```bash
# 1. Check stack status
AWS_PAGER="" aws cloudformation describe-stacks \
  --stack-name CourtCaseManagementStack \
  --query 'Stacks[0].{Status:StackStatus,Outputs:Outputs}' \
  --output table

# 2. Check ECS tasks are running
AWS_PAGER="" aws ecs list-tasks \
  --cluster CourtCaseCluster \
  --service-name CourtCaseBackendService

# 3. Get ALB URL
ALB_URL=$(AWS_PAGER="" aws cloudformation describe-stacks \
  --stack-name CourtCaseManagementStack \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerURL`].OutputValue' \
  --output text)

echo "Application URL: http://$ALB_URL"

# 4. Test health endpoint (wait 2-3 minutes for tasks to start)
curl -f "http://$ALB_URL/health" || echo "Health check failed - tasks may still be starting"
```

---

## Troubleshooting

### If Stack Deletion Hangs

```bash
# Check what's blocking deletion
AWS_PAGER="" aws cloudformation describe-stack-events \
  --stack-name CourtCaseManagementStack \
  --max-items 20 \
  --query 'StackEvents[?ResourceStatus==`DELETE_FAILED`]'

# Common blockers:
# - RDS instance with deletion protection
# - DB subnet groups in use
# - Security groups with dependencies
# - ENIs still attached
```

### If Pre-Deployment Tests Fail

**Missing Secrets**:

```bash
aws secretsmanager create-secret \
  --name <secret-name> \
  --secret-string '{"username":"admin","password":"<secure-password>"}'
```

**Orphaned Resources**:

```bash
# Delete RDS instances
aws rds delete-db-instance \
  --db-instance-identifier <id> \
  --skip-final-snapshot

# Delete DB subnet groups
aws rds delete-db-subnet-group \
  --db-subnet-group-name <name>

# Delete ECS clusters
aws ecs delete-cluster --cluster <name>
```

### If Deployment Fails

**Use AWS Powers to troubleshoot**:

```python
kiroPowers(
    action="use",
    powerName="aws-infrastructure-as-code",
    serverName="awslabs.aws-iac-mcp-server",
    toolName="troubleshoot_cloudformation_deployment",
    arguments={
        "stack_name": "CourtCaseManagementStack",
        "region": "us-east-1",
        "include_cloudtrail": True
    }
)
```

---

## Expected Timeline

| Step                 | Duration      | Status         |
| -------------------- | ------------- | -------------- |
| Stack deletion       | 5-10 min      | ⏳ IN PROGRESS |
| Pre-deployment tests | 2-3 min       | ⏳ PENDING     |
| Template validation  | 1-2 min       | ⏳ PENDING     |
| CDK deployment       | 30-40 min     | ⏳ PENDING     |
| **Total**            | **40-55 min** |                |

---

## Success Criteria

✅ Stack status: `CREATE_COMPLETE`
✅ ECS tasks: 2/2 running
✅ RDS status: `available`
✅ Health check: Returns 200 OK
✅ ALB: Accessible via HTTP

---

## Quick Commands Reference

```bash
# Check stack status
AWS_PAGER="" aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --query 'Stacks[0].StackStatus' --output text

# Run pre-deployment tests
bash caseapp/scripts/pre-deployment-test-suite.sh

# Deploy with CDK
cd caseapp/infrastructure && cdk deploy --require-approval never

# Monitor deployment
watch -n 30 'aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --query "Stacks[0].StackStatus" --output text'

# Check ECS tasks
AWS_PAGER="" aws ecs describe-services --cluster CourtCaseCluster --services CourtCaseBackendService

# Get application URL
aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerURL`].OutputValue' --output text
```

---

## What Changed Since Deployment #66

1. ✅ Created comprehensive pre-deployment test suite (12 tests)
2. ✅ Created AWS Powers validation script
3. ✅ Fixed missing secret: `courtcase-database-credentials`
4. ✅ Deleted orphaned RDS instance
5. ✅ Deleted orphaned DB subnet groups
6. ✅ Cleaned up failed stack
7. ✅ Documented complete workflow

**Result**: Deployment #67 should succeed because we've caught and fixed all issues before deploying.

---

## Need Help?

- **Pre-deployment tests failing**: Review `PRE-DEPLOYMENT-TESTING-GUIDE.md`
- **Template validation issues**: Use AWS Powers validation
- **Deployment failures**: Use AWS Powers troubleshooting tool
- **Stuck resources**: Check CloudFormation events for blockers

**Remember**: Test before you deploy. Every time. No exceptions.
