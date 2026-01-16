# Deployment #75 Root Cause Analysis

## Summary

Deployment #75 failed with `InvalidChangeSetStatusException: Cannot delete ChangeSet in status CREATE_IN_PROGRESS` error, but the CloudFormation stack is actually being created successfully in the background.

## Error Details

**GitHub Actions Run**: #75 (ID: 21041037614)
**Failed Job**: deploy-staging
**Error Message**:

```
❌  CourtCaseManagementStack failed: InvalidChangeSetStatusException: Cannot delete ChangeSet in status CREATE_IN_PROGRESS
Error: Process completed with exit code 1.
```

**Time**: Failed after 42 seconds in the deploy-staging job

## Root Cause

This is a **CDK race condition bug**, not an infrastructure failure. The issue occurs when:

1. CDK creates a ChangeSet named `cdk-deploy-change-set`
2. The ChangeSet enters `CREATE_IN_PROGRESS` state
3. CDK tries to delete/replace the ChangeSet before it finishes creating
4. CloudFormation rejects the delete operation with `InvalidChangeSetStatusException`
5. CDK exits with error code 1, failing the GitHub Actions workflow

**However**: The CloudFormation stack creation continues in the background despite the CDK error.

## Current Stack Status

As of analysis time (40+ minutes after deployment started):

- Stack Status: `CREATE_IN_PROGRESS`
- ECS Services: Created and running (4 tasks running, 2 desired)
- ECS Task Health: `UNKNOWN` (health checks not passed yet)
- No failed resources detected

The stack is progressing normally and will likely complete successfully.

## Why This Happened

CDK's default behavior is to:

1. Create a ChangeSet
2. Execute the ChangeSet
3. Delete the ChangeSet after execution

When deployments are slow (RDS creation, ECS service stabilization), CDK can encounter timing issues where it tries to delete a ChangeSet that's still being processed by CloudFormation.

## Impact

- **GitHub Actions**: Workflow failed and marked as failed
- **CloudFormation**: Stack creation continues normally
- **Infrastructure**: Being deployed successfully despite workflow failure
- **User Experience**: Confusing - workflow shows failure but infrastructure is actually working

## Solution

### Immediate Fix

Add `--no-rollback` flag to CDK deploy command to prevent aggressive ChangeSet cleanup:

```yaml
- name: Deploy with CDK
  working-directory: caseapp/infrastructure
  run: |
    cdk deploy --all --require-approval never --no-rollback
```

### Alternative Fix

Use `--method=direct` to skip ChangeSet creation entirely:

```yaml
- name: Deploy with CDK
  working-directory: caseapp/infrastructure
  run: |
    cdk deploy --all --require-approval never --method=direct
```

### Long-term Fix

1. Add retry logic for CDK deploy failures
2. Check CloudFormation stack status after CDK exits
3. Only fail the workflow if the stack actually failed
4. Add timeout handling for long-running deployments

## Verification Steps

After applying the fix:

1. Trigger new deployment
2. Monitor for `InvalidChangeSetStatusException` error
3. Verify CDK completes without errors
4. Confirm stack reaches `CREATE_COMPLETE` status

## Related Issues

- Deployment #73: Failed due to Slack MCP not available in CI/CD
- Deployment #74: Failed due to stuck CloudFormation stack from #73
- Deployment #75: Failed due to CDK ChangeSet race condition

## Recommendations

1. **Apply immediate fix**: Add `--no-rollback` to CDK deploy
2. **Monitor current deployment**: Check if stack completes successfully despite CDK error
3. **Test fix**: Trigger deployment #76 with the fix applied
4. **Consider direct method**: If `--no-rollback` doesn't work, use `--method=direct`

## Files to Modify

- `.github/workflows/ci-cd.yml` - Add `--no-rollback` flag to CDK deploy steps

## Next Steps

1. Wait for current stack to complete or fail
2. Apply fix to workflow
3. Trigger deployment #76
4. Monitor for success
