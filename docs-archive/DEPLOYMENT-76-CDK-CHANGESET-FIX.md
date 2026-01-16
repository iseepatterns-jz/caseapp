# Deployment #76 - CDK ChangeSet Race Condition Fix

## Problem Summary

Deployments #75 and #76 both failed with the same error:

```
❌ CourtCaseManagementStack failed: InvalidChangeSetStatusException: Cannot delete ChangeSet in status CREATE_IN_PROGRESS
```

This is a known CDK race condition bug where CDK tries to delete a ChangeSet that's still being created by CloudFormation.

## Root Cause

**CDK Default Deployment Method**: By default, CDK uses `--method=change-set` which:

1. Creates a CloudFormation ChangeSet
2. Waits for ChangeSet to be ready
3. Executes the ChangeSet
4. Deletes the ChangeSet after execution

**The Race Condition**: Sometimes CDK tries to delete the ChangeSet before CloudFormation finishes creating it, causing the `InvalidChangeSetStatusException`.

## Solutions (3 Options)

### Option 1: Use Direct Deployment Method (RECOMMENDED)

**What**: Use `--method=direct` to bypass ChangeSet creation entirely.

**Pros**:

- Completely avoids the ChangeSet race condition
- Faster deployments (no ChangeSet creation overhead)
- Simpler deployment process

**Cons**:

- Lose detailed deployment progress in CLI output
- Can't preview changes before deployment (but we can use `cdk diff` for that)

**Implementation**:

```yaml
# In .github/workflows/ci-cd.yml
- name: Deploy with CDK
  run: |
    cd caseapp/infrastructure
    cdk deploy --all --require-approval never --method=direct
```

### Option 2: Use Prepare-Change-Set Method

**What**: Use `--method=prepare-change-set` to create ChangeSet without executing it, then execute separately.

**Pros**:

- Separates ChangeSet creation from execution
- Can inspect ChangeSet before executing
- More control over deployment process

**Cons**:

- More complex (requires two steps)
- Slower than direct method
- Still uses ChangeSets (may have other issues)

**Implementation**:

```yaml
# In .github/workflows/ci-cd.yml
- name: Create Change Set
  run: |
    cd caseapp/infrastructure
    cdk deploy --all --require-approval never --method=prepare-change-set

- name: Execute Change Set
  run: |
    # Execute the change set using AWS CLI
    aws cloudformation execute-change-set \
      --change-set-name cdk-deploy-change-set \
      --stack-name CourtCaseManagementStack

    # Wait for execution to complete
    aws cloudformation wait stack-update-complete \
      --stack-name CourtCaseManagementStack
```

### Option 3: Keep Change-Set Method with Retry Logic

**What**: Keep using `--method=change-set` but add retry logic to handle the race condition.

**Pros**:

- Keeps detailed deployment progress
- Maintains current deployment method
- Eventually succeeds after retries

**Cons**:

- Doesn't fix the root cause
- Wastes time on retries
- May still fail after max retries

**Implementation**:

```yaml
# In .github/workflows/ci-cd.yml
- name: Deploy with CDK (with retry)
  run: |
    cd caseapp/infrastructure
    max_attempts=3
    attempt=1

    while [ $attempt -le $max_attempts ]; do
      echo "Deployment attempt $attempt of $max_attempts"
      
      if cdk deploy --all --require-approval never --no-rollback; then
        echo "Deployment successful!"
        exit 0
      else
        if [ $attempt -lt $max_attempts ]; then
          echo "Deployment failed, waiting 30 seconds before retry..."
          sleep 30
        fi
      fi
      
      attempt=$((attempt + 1))
    done

    echo "Deployment failed after $max_attempts attempts"
    exit 1
```

## Recommended Solution

**Use Option 1: Direct Deployment Method**

Reasons:

1. **Completely eliminates the race condition** - No ChangeSet = No race condition
2. **Faster deployments** - Skips ChangeSet creation overhead
3. **Simpler code** - No retry logic or multi-step process needed
4. **We can still preview changes** - Use `cdk diff` before deploying

## Implementation Steps

### Step 1: Update Workflow File

```bash
# Edit .github/workflows/ci-cd.yml
```

Change both staging and production deploy steps from:

```yaml
cdk deploy --all --require-approval never --no-rollback
```

To:

```yaml
cdk deploy --all --require-approval never --method=direct
```

**Note**: Remove `--no-rollback` flag since `--method=direct` doesn't use ChangeSets (rollback is a ChangeSet feature).

### Step 2: Add Pre-Deployment Diff (Optional)

To maintain visibility into changes, add a diff step before deployment:

```yaml
- name: Show deployment changes
  run: |
    cd caseapp/infrastructure
    cdk diff || true  # Don't fail if diff shows changes

- name: Deploy with CDK
  run: |
    cd caseapp/infrastructure
    cdk deploy --all --require-approval never --method=direct
```

### Step 3: Test Locally

Before pushing, test the direct method locally:

```bash
cd caseapp/infrastructure

# Show what will change
cdk diff

# Deploy using direct method
cdk deploy --all --method=direct
```

### Step 4: Commit and Deploy

```bash
git add .github/workflows/ci-cd.yml
git commit -m "fix: use direct deployment method to avoid CDK ChangeSet race condition"
git push origin main
```

### Step 5: Verify Clean Environment

Before triggering deployment:

1. Run `cdk destroy --all --force`
2. Run `verify-resources-before-deploy.sh`
3. Check browser - CloudFormation console (no stacks)
4. Check browser - GitHub Actions (no running workflows)
5. Only then trigger deployment

## Additional Improvements

### 1. Add Deployment Method Documentation

Document the deployment method choice in the infrastructure README:

````markdown
## Deployment Method

This project uses `--method=direct` for CDK deployments to avoid the ChangeSet race condition bug.

To preview changes before deploying:

```bash
cdk diff
```
````

To deploy:

```bash
cdk deploy --all --method=direct
```

````

### 2. Update Pre-Deployment Verification

The verification script should also check for in-progress ChangeSets:

```bash
# In verify-resources-before-deploy.sh
echo "Checking for in-progress ChangeSets..."
changesets=$(aws cloudformation list-change-sets \
  --stack-name CourtCaseManagementStack 2>/dev/null | \
  jq -r '.Summaries[] | select(.Status == "CREATE_IN_PROGRESS") | .ChangeSetName' || true)

if [ -n "$changesets" ]; then
  echo "⚠️  Found in-progress ChangeSets: $changesets"
  issues=$((issues + 1))
fi
````

### 3. Add Deployment Monitoring

Monitor deployments for the direct method (which doesn't show detailed progress):

```bash
# After cdk deploy --method=direct
echo "Monitoring stack status..."
aws cloudformation wait stack-update-complete \
  --stack-name CourtCaseManagementStack

echo "Deployment complete! Checking stack status..."
aws cloudformation describe-stacks \
  --stack-name CourtCaseManagementStack \
  --query 'Stacks[0].StackStatus'
```

## Testing Plan

1. **Local Testing**:

   - Test `cdk deploy --method=direct` locally
   - Verify deployment succeeds
   - Verify resources are created correctly

2. **CI/CD Testing**:

   - Trigger deployment #77 with direct method
   - Monitor for ChangeSet errors (should not occur)
   - Verify deployment completes successfully

3. **Rollback Testing**:
   - Test `cdk destroy` still works with direct method
   - Verify clean resource deletion

## Expected Outcome

- ✅ No more `InvalidChangeSetStatusException` errors
- ✅ Faster deployments (no ChangeSet overhead)
- ✅ Simpler deployment process
- ✅ Same end result (resources deployed correctly)

## References

- [CDK Deploy Documentation](https://docs.aws.amazon.com/cdk/v2/guide/ref-cli-cmd-deploy.html)
- [CDK Deployment Methods](https://docs.aws.amazon.com/cdk/v2/guide/toolkit-library-actions.html)
- AWS Powers search results on CDK deployment options

## Next Steps

1. Implement Option 1 (direct method) in workflow
2. Test locally to verify it works
3. Follow pre-deployment verification checklist
4. Trigger deployment #77
5. Monitor for success
6. Document the fix in deployment runbook
