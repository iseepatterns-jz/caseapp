# Fast-Track Deployment Plan - Day 5

## Goal: Get ONE successful deployment TODAY

## Current Situation

- 5 days of failed deployments
- Multiple issues: ChangeSet race condition, concurrent deployments, stuck stacks
- OpenSearch already disabled (saves 16 minutes)
- RDS deletion protection disabled (for testing)

## Fast-Track Strategy

### Phase 1: Apply ALL Fixes at Once (10 minutes)

#### Fix 1: Use Direct Deployment Method

```yaml
# In .github/workflows/ci-cd.yml
# Change from:
cdk deploy --all --require-approval never --no-rollback

# To:
cdk deploy --all --require-approval never --method=direct
```

**Why**: Eliminates ChangeSet race condition completely

#### Fix 2: Reduce Infrastructure Scope (TEMPORARY)

```python
# In caseapp/infrastructure/app.py
# Comment out EVERYTHING except VPC and one minimal ECS service

# Keep only:
# - VPC
# - Security Groups
# - ECS Cluster (no tasks yet)
# - ALB (minimal config)

# Comment out for now:
# - RDS (add later)
# - Redis (add later)
# - S3 buckets (add later)
# - All ECS services (add later)
```

**Why**: Deploy minimal infrastructure first, add components incrementally

#### Fix 3: Use Smaller Instance Types

```python
# In caseapp/infrastructure/app.py
# Change ECS task sizes:
cpu=256,      # Was 512
memory=512,   # Was 1024
```

**Why**: Faster provisioning, lower cost during testing

### Phase 2: Clean Environment (5 minutes)

```bash
# 1. Destroy everything
cd caseapp/infrastructure
cdk destroy --all --force

# 2. Verify with script
cd ../..
bash verify-resources-before-deploy.sh

# 3. Verify in browser (use Chrome DevTools MCP)
# - CloudFormation: No stacks
# - GitHub Actions: No running workflows
```

### Phase 3: Deploy Minimal Stack (15-20 minutes)

```bash
# 1. Synthesize to check for errors
cd caseapp/infrastructure
cdk synth

# 2. Show what will be deployed
cdk diff

# 3. Deploy with direct method
cdk deploy --all --method=direct --require-approval never

# Expected time: 15-20 minutes (no RDS, no Redis, no ECS tasks)
```

### Phase 4: Verify Success (2 minutes)

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name CourtCaseManagementStack \
  --query 'Stacks[0].StackStatus'

# Should show: CREATE_COMPLETE or UPDATE_COMPLETE
```

### Phase 5: Add Components Incrementally (Optional)

Once minimal stack succeeds, add components one at a time:

1. **Add Redis** (5 minutes to deploy)
2. **Add RDS** (15 minutes to deploy)
3. **Add S3 buckets** (2 minutes to deploy)
4. **Add ECS services** (10 minutes to deploy)

Each deployment uses `cdk deploy --method=direct`

## Minimal Infrastructure Code

Here's the absolute minimum to deploy:

```python
# caseapp/infrastructure/app.py (MINIMAL VERSION)
from aws_cdk import (
    App,
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
)

app = App()

class MinimalStack(Stack):
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # VPC
        vpc = ec2.Vpc(
            self, "VPC",
            max_azs=2,
            nat_gateways=1  # Minimal NAT gateways
        )

        # ECS Cluster (empty for now)
        cluster = ecs.Cluster(
            self, "Cluster",
            vpc=vpc,
            cluster_name="court-case-cluster"
        )

        # ALB (minimal)
        alb = elbv2.ApplicationLoadBalancer(
            self, "ALB",
            vpc=vpc,
            internet_facing=True
        )

        # That's it! Just VPC + Cluster + ALB

stack = MinimalStack(app, "CourtCaseManagementStack")
app.synth()
```

**Deployment time**: ~10 minutes

## Alternative: Skip CDK Entirely (FASTEST)

If CDK keeps failing, deploy manually with CloudFormation:

```yaml
# minimal-stack.yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: Minimal test stack

Resources:
  TestBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub "court-case-test-${AWS::AccountId}"

Outputs:
  BucketName:
    Value: !Ref TestBucket
```

Deploy:

```bash
aws cloudformation create-stack \
  --stack-name CourtCaseTest \
  --template-body file://minimal-stack.yaml

# Wait for completion (2 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name CourtCaseTest
```

**Deployment time**: ~2 minutes

## Recommended Approach: Minimal CDK First

1. **Backup current app.py**:

   ```bash
   cp caseapp/infrastructure/app.py caseapp/infrastructure/app.py.full
   ```

2. **Create minimal app.py** (use code above)

3. **Deploy minimal stack**:

   ```bash
   cd caseapp/infrastructure
   cdk deploy --method=direct
   ```

4. **Once successful, gradually add components**

## Time Estimates

| Approach                      | Time to First Success | Risk     |
| ----------------------------- | --------------------- | -------- |
| Minimal CDK (VPC+Cluster+ALB) | 10-15 min             | Low      |
| Minimal CDK (VPC only)        | 5-10 min              | Very Low |
| CloudFormation (S3 only)      | 2 min                 | Very Low |
| Full stack with fixes         | 30-40 min             | Medium   |

## Decision Matrix

**If you want success ASAP**: Use Minimal CDK (VPC only)
**If you want to test full stack**: Apply all fixes and deploy full stack
**If CDK keeps failing**: Use CloudFormation directly

## Execution Plan (Next 30 Minutes)

### Option A: Minimal CDK (RECOMMENDED)

```bash
# 1. Clean environment (5 min)
cd caseapp/infrastructure
cdk destroy --all --force
cd ../..
bash verify-resources-before-deploy.sh

# 2. Backup and create minimal app.py (2 min)
cp caseapp/infrastructure/app.py caseapp/infrastructure/app.py.full
# Create minimal version (VPC + Cluster + ALB only)

# 3. Deploy (10 min)
cd caseapp/infrastructure
cdk deploy --method=direct --require-approval never

# 4. Verify success (1 min)
aws cloudformation describe-stacks --stack-name CourtCaseManagementStack

# Total: ~18 minutes to first success
```

### Option B: Full Stack with All Fixes

```bash
# 1. Apply workflow fix (2 min)
# Edit .github/workflows/ci-cd.yml
# Change to --method=direct

# 2. Clean environment (5 min)
cd caseapp/infrastructure
cdk destroy --all --force
cd ../..
bash verify-resources-before-deploy.sh

# 3. Commit and push (1 min)
git add .github/workflows/ci-cd.yml
git commit -m "fix: use direct deployment method"
git push origin main

# 4. Trigger deployment (1 min)
gh workflow run "CI/CD Pipeline" --ref main

# 5. Wait for deployment (30-40 min)
# Monitor in browser

# Total: ~40-50 minutes to first success
```

## What I Recommend RIGHT NOW

**Do Option A (Minimal CDK) locally first**:

1. This proves CDK works with direct method
2. Gets you a success in 15-20 minutes
3. Builds confidence before full deployment
4. Allows incremental addition of components

Once minimal works, you can:

- Add components one by one
- Or restore full app.py and deploy via GitHub Actions

## Critical Success Factors

1. ✅ Use `--method=direct` (no ChangeSet)
2. ✅ Clean environment first (destroy + verify)
3. ✅ Start minimal, add incrementally
4. ✅ No concurrent deployments
5. ✅ Monitor actively

## Let's Get This Done

Which approach do you want to take?

**A) Minimal CDK locally** (15-20 min to success)
**B) Full stack with fixes via GitHub Actions** (40-50 min to success)
**C) Ultra-minimal CloudFormation** (2 min to success, but not real infrastructure)

I recommend **Option A** - it's the fastest path to a real success with actual infrastructure.
