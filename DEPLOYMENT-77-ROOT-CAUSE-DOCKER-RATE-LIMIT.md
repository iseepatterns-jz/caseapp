# Deployment #77 Root Cause: Docker Hub Rate Limiting

**Date**: 2026-01-15  
**Issue**: Docker Hub rate limit preventing container pulls  
**Impact**: ECS tasks cannot start, health checks fail, deployment stuck

## Root Cause

**Docker Hub Rate Limiting**: ECS tasks are hitting Docker Hub's unauthenticated pull rate limit (429 Too Many Requests).

### Error Message

```
CannotPullContainerError: pull image manifest has been retried 7 time(s):
httpReadSeeker: failed open: unexpected status code
https://registry-1.docker.io/v2/iseepatterns/court-case-backend/manifests/sha256:d1faca3f650b469373dcd774fba31726af5252f4dd2435e6aee308dff5e8d3f1:
429 Too Many Requests - Server message: toomanyrequests:
You have reached your unauthenticated pull rate limit.
https://www.docker.com/increase-rate-limit
```

### Why This Happens

Docker Hub has rate limits for unauthenticated pulls:

- **Free tier (unauthenticated)**: 100 pulls per 6 hours per IP address
- **Free tier (authenticated)**: 200 pulls per 6 hours
- **Pro/Team**: Higher limits

ECS is pulling images without Docker Hub authentication, hitting the free tier limit.

## Impact Chain

1. **ECS tries to start tasks** → Pulls image from Docker Hub
2. **Docker Hub rejects pull** → 429 Too Many Requests
3. **Task fails to start** → No container running
4. **No logs written** → Container never starts
5. **Health checks fail** → No application to check
6. **Stack stuck** → Waiting for healthy tasks that will never come

## Solutions

### Option 1: Use Amazon ECR (Recommended)

Push your Docker images to Amazon Elastic Container Registry instead of Docker Hub.

**Advantages**:

- No rate limits
- Faster pulls (same region)
- Better security (private by default)
- Integrated with AWS IAM

**Steps**:

```bash
# 1. Create ECR repository
aws ecr create-repository --repository-name court-case-backend --region us-east-1

# 2. Get ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 730335557645.dkr.ecr.us-east-1.amazonaws.com

# 3. Tag your image
docker tag iseepatterns/court-case-backend:latest 730335557645.dkr.ecr.us-east-1.amazonaws.com/court-case-backend:latest

# 4. Push to ECR
docker push 730335557645.dkr.ecr.us-east-1.amazonaws.com/court-case-backend:latest

# 5. Update CDK code to use ECR image
# In caseapp/infrastructure/app.py, change:
# image=ecs.ContainerImage.from_registry(f"{docker_username}/court-case-backend:latest")
# to:
# image=ecs.ContainerImage.from_registry("730335557645.dkr.ecr.us-east-1.amazonaws.com/court-case-backend:latest")
```

### Option 2: Add Docker Hub Authentication

Store Docker Hub credentials in AWS Secrets Manager and configure ECS to use them.

**Steps**:

```bash
# 1. Create secret with Docker Hub credentials
aws secretsmanager create-secret \
  --name dockerhub-credentials \
  --secret-string '{"username":"iseepatterns","password":"YOUR_DOCKER_HUB_TOKEN"}' \
  --region us-east-1

# 2. Update CDK code to use credentials
# Add to task definition:
repository_credentials=ecs.RepositoryCredentials.from_secrets_manager(
    secret=secretsmanager.Secret.from_secret_name_v2(
        self, "DockerHubSecret",
        secret_name="dockerhub-credentials"
    )
)
```

### Option 3: Use GitHub Container Registry

Push images to GitHub Container Registry (ghcr.io) which has higher rate limits.

**Steps**:

```bash
# 1. Create GitHub personal access token with packages:write scope

# 2. Login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u iseepatterns-jz --password-stdin

# 3. Tag and push
docker tag iseepatterns/court-case-backend:latest ghcr.io/iseepatterns-jz/court-case-backend:latest
docker push ghcr.io/iseepatterns-jz/court-case-backend:latest

# 4. Update CDK code
# image=ecs.ContainerImage.from_registry("ghcr.io/iseepatterns-jz/court-case-backend:latest")
```

## Recommended Solution: Amazon ECR

**Why ECR is best**:

1. ✅ No rate limits
2. ✅ Faster (same region as ECS)
3. ✅ More secure (private by default)
4. ✅ Better integration with AWS services
5. ✅ No external dependencies
6. ✅ Included in AWS Free Tier (500 MB storage/month)

## Implementation Plan

### Step 1: Clean Up Current Deployment

```bash
cd caseapp/infrastructure
cdk destroy --all --force
```

### Step 2: Set Up ECR

```bash
# Create repository
aws ecr create-repository \
  --repository-name court-case-backend \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256

# Get repository URI
aws ecr describe-repositories \
  --repository-names court-case-backend \
  --region us-east-1 \
  --query 'repositories[0].repositoryUri' \
  --output text
```

### Step 3: Build and Push Image

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  730335557645.dkr.ecr.us-east-1.amazonaws.com

# Build image (if needed)
cd caseapp
docker build -t court-case-backend:latest -f Dockerfile .

# Tag for ECR
docker tag court-case-backend:latest \
  730335557645.dkr.ecr.us-east-1.amazonaws.com/court-case-backend:latest

# Push to ECR
docker push 730335557645.dkr.ecr.us-east-1.amazonaws.com/court-case-backend:latest
```

### Step 4: Update CDK Code

```python
# In caseapp/infrastructure/app.py, line ~470
# Change from:
image=ecs.ContainerImage.from_registry(f"{docker_username}/court-case-backend:latest")

# To:
image=ecs.ContainerImage.from_registry(
    "730335557645.dkr.ecr.us-east-1.amazonaws.com/court-case-backend:latest"
)
```

### Step 5: Update GitHub Actions Workflow

```yaml
# In .github/workflows/ci-cd.yml
# Add ECR login and push steps before CDK deploy:

- name: Login to Amazon ECR
  run: |
    aws ecr get-login-password --region us-east-1 | \
      docker login --username AWS --password-stdin \
      730335557645.dkr.ecr.us-east-1.amazonaws.com

- name: Build and push Docker image
  run: |
    cd caseapp
    docker build -t court-case-backend:latest -f Dockerfile .
    docker tag court-case-backend:latest \
      730335557645.dkr.ecr.us-east-1.amazonaws.com/court-case-backend:latest
    docker push 730335557645.dkr.ecr.us-east-1.amazonaws.com/court-case-backend:latest
```

### Step 6: Deploy

```bash
# Verify resources are clean
bash verify-resources-before-deploy.sh

# Deploy
cd caseapp/infrastructure
cdk deploy
```

## Why Previous Deployments Worked

Previous deployments may have worked because:

1. Different IP addresses (GitHub Actions runners)
2. Earlier in the 6-hour rate limit window
3. Fewer total pulls across all deployments
4. Rate limit resets every 6 hours

## Prevention

To prevent this in the future:

1. ✅ Use ECR for all production images
2. ✅ Add Docker Hub authentication for development
3. ✅ Monitor ECR usage and costs
4. ✅ Set up image lifecycle policies in ECR
5. ✅ Use image scanning in ECR for security

## Cost Considerations

**ECR Pricing** (us-east-1):

- Storage: $0.10 per GB/month
- Data transfer: Free within same region
- Typical usage: ~500 MB for backend image = $0.05/month
- **Free Tier**: 500 MB storage/month for 12 months

**Comparison**:

- Docker Hub Free: Rate limited, public images
- Docker Hub Pro ($5/month): Higher limits, private repos
- ECR: No rate limits, ~$0.05/month for typical usage

**Recommendation**: Use ECR - it's cheaper and better integrated.

## Summary

**Problem**: Docker Hub rate limiting preventing ECS tasks from pulling images.

**Solution**: Migrate to Amazon ECR to eliminate rate limits and improve performance.

**Next Steps**:

1. Clean up current deployment
2. Create ECR repository
3. Push image to ECR
4. Update CDK code to use ECR
5. Redeploy

**Estimated Time**: 15-20 minutes to implement, 30-40 minutes to deploy.

**Success Criteria**: ECS tasks start successfully, health checks pass, stack completes.
