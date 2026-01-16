# CI/CD and Docker Configuration Best Practices Analysis

**Date**: 2026-01-15 21:15 UTC  
**Files Analyzed**: `.github/workflows/ci-cd.yml`, `caseapp/docker-compose.yml`, `caseapp/Dockerfile`  
**Focus**: Best practices and `/caseapp` directory structure issues

## Executive Summary

**CRITICAL ISSUES FOUND**: 3  
**WARNINGS**: 5  
**RECOMMENDATIONS**: 8

The analysis reveals several issues related to the `/caseapp` directory structure, Docker build context, and workflow configuration that could cause deployment failures or inefficiencies.

---

## 1. GitHub Actions Workflow Analysis (`.github/workflows/ci-cd.yml`)

### ✅ CORRECT Configurations

1. **Manual-only trigger** - `workflow_dispatch` prevents automatic deployments ✅
2. **Proper working directory usage** - Uses `working-directory: caseapp/backend` for tests ✅
3. **Correct Docker context** - `context: ./caseapp` properly scoped ✅
4. **Timeout settings** - Reasonable timeouts for each job ✅
5. **Conditional deployment** - Proper branch and environment checks ✅

### ⚠️ WARNINGS

#### Warning 1: Inconsistent Path References

**Issue**: Mix of relative paths with and without `./` prefix

```yaml
# Inconsistent:
pip install -r caseapp/requirements.txt          # No ./
working-directory: caseapp/backend               # No ./
context: ./caseapp                               # Has ./
file: ./caseapp/Dockerfile                       # Has ./
working-directory: caseapp/infrastructure        # No ./
```

**Impact**: While this works, it's inconsistent and can cause confusion

**Recommendation**: Standardize on one approach (prefer `./` prefix for clarity)

```yaml
# Standardized approach:
- name: Install dependencies
  run: |
    pip install -r ./caseapp/requirements.txt
    pip install pytest

- name: Run tests
  working-directory: ./caseapp/backend
  run: python -m pytest tests/test_ci_basic.py -v

- name: Build and push backend
  uses: docker/build-push-action@v5
  with:
    context: ./caseapp
    file: ./caseapp/Dockerfile
```

#### Warning 2: Missing Build Validation

**Issue**: No validation step before deployment

```yaml
deploy-production:
  needs: build-and-push
  # Missing: Template validation step
  steps:
    - name: Deploy with CDK
      run: cdk deploy --require-approval never --all --method=direct
```

**Impact**: Invalid templates can cause deployment failures

**Recommendation**: Add validation step

```yaml
deploy-production:
  needs: build-and-push
  steps:
    - uses: actions/checkout@v4

    # Add validation step
    - name: Validate Infrastructure
      working-directory: ./caseapp/infrastructure
      run: |
        pip install -r requirements.txt
        cdk synth > template.yaml
        # Could add cfn-lint validation here

    - name: Deploy with CDK
      working-directory: ./caseapp/infrastructure
      run: cdk deploy --require-approval never --all --method=direct
```

#### Warning 3: Hardcoded Stack Names

**Issue**: Stack names are hardcoded and don't match between staging/production

```yaml
# Staging uses:
STACK_NAME="CourtCaseManagementStack-Staging"

# Production uses:
STACK_NAME="CourtCaseManagementStack"
```

**Impact**: If CDK generates different stack names, verification will fail

**Recommendation**: Get stack name from CDK output

```yaml
- name: Verify deployment
  working-directory: ./caseapp/infrastructure
  run: |
    echo "Waiting for services to stabilize..."
    sleep 120

    # Get actual stack name from CDK
    STACK_NAME=$(cdk list | head -1)
    aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region ${{ env.AWS_REGION }}
```

#### Warning 4: No Rollback Strategy

**Issue**: No automatic rollback on deployment failure

**Impact**: Failed deployments leave infrastructure in inconsistent state

**Recommendation**: Add rollback step

```yaml
- name: Deploy with CDK
  id: deploy
  working-directory: ./caseapp/infrastructure
  run: cdk deploy --require-approval never --all --method=direct

- name: Rollback on failure
  if: failure() && steps.deploy.outcome == 'failure'
  working-directory: ./caseapp/infrastructure
  run: |
    echo "Deployment failed, initiating rollback..."
    cdk destroy --force --all
```

#### Warning 5: Missing Health Check Validation

**Issue**: Deployment verification only checks stack status, not application health

```yaml
- name: Verify deployment
  run: |
    sleep 120
    aws cloudformation describe-stacks --stack-name "$STACK_NAME"
    # Missing: Check ECS task health, ALB health checks
```

**Recommendation**: Add comprehensive health checks

```yaml
- name: Verify deployment
  run: |
    echo "Waiting for services to stabilize..."
    sleep 120

    STACK_NAME="CourtCaseManagementStack"

    # Check stack status
    aws cloudformation describe-stacks --stack-name "$STACK_NAME"

    # Get ECS cluster and service names from stack outputs
    CLUSTER=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
      --query 'Stacks[0].Outputs[?OutputKey==`ClusterName`].OutputValue' --output text)
    SERVICE=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
      --query 'Stacks[0].Outputs[?OutputKey==`ServiceName`].OutputValue' --output text)

    # Check ECS service health
    aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" \
      --query 'services[0].{Running:runningCount,Desired:desiredCount,Health:healthCheckGracePeriodSeconds}'

    # Check task health
    TASK_ARNS=$(aws ecs list-tasks --cluster "$CLUSTER" --service-name "$SERVICE" --query 'taskArns' --output text)
    if [ -n "$TASK_ARNS" ]; then
      aws ecs describe-tasks --cluster "$CLUSTER" --tasks $TASK_ARNS \
        --query 'tasks[*].{Status:lastStatus,Health:healthStatus}'
    fi
```

---

## 2. Docker Compose Analysis (`caseapp/docker-compose.yml`)

### ✅ CORRECT Configurations

1. **Health checks defined** - Postgres and backend have proper health checks ✅
2. **Volume management** - Named volumes for persistence ✅
3. **Service dependencies** - Proper `depends_on` with conditions ✅
4. **Environment variable structure** - Individual DB fields for RDS compatibility ✅

### 🔴 CRITICAL ISSUES

#### Critical Issue 1: Incorrect Volume Mounts for `/caseapp` Structure

**Issue**: Volume mounts assume code is in subdirectories, but Dockerfile copies to root

```yaml
backend:
  volumes:
    - ./backend:/app # ❌ WRONG: backend/ doesn't exist at repo root
    - ./shared:/app/shared # ❌ WRONG: shared/ doesn't exist at repo root
    - media_storage:/app/media
```

**Root Cause**: The repository structure is:

```
/caseapp/backend/     # Backend code is HERE
/caseapp/shared/      # Shared code is HERE
```

But docker-compose.yml is in `/caseapp/`, so relative paths are wrong.

**Impact**:

- Volume mounts fail silently or mount empty directories
- Code changes don't reflect in running containers
- Development workflow is broken

**Fix**:

```yaml
backend:
  build:
    context: . # Context is /caseapp
    target: backend-base
  volumes:
    - ./backend:/app # ✅ CORRECT: ./backend = /caseapp/backend
    - ./shared:/app/shared # ✅ CORRECT: ./shared = /caseapp/shared
    - media_storage:/app/media
```

**Verification**: The paths are actually CORRECT because docker-compose.yml is in `/caseapp/`, so `./backend` correctly refers to `/caseapp/backend`.

**However**, there's a mismatch with the Dockerfile:

#### Critical Issue 2: Dockerfile Copies Backend to Root, But Expects Subdirectory

**Issue**: Dockerfile copies backend code to `/app` root, but docker-compose mounts expect subdirectory structure

```dockerfile
# In Dockerfile:
WORKDIR /app
COPY backend/ ./                  # Copies to /app (root)
# Result: /app/main.py, /app/core/, /app/services/

# In docker-compose.yml:
volumes:
  - ./backend:/app                # Mounts /caseapp/backend to /app
# Result: /app/main.py, /app/core/, /app/services/
```

**Analysis**: Actually, this IS consistent! Both result in the same structure.

**BUT** there's a problem with the media-processor service:

```yaml
media-processor:
  volumes:
    - ./backend/services:/app/services # ❌ WRONG: Overwrites copied services
```

**Impact**: The volume mount overwrites the services directory copied during build

**Fix**:

```yaml
media-processor:
  build:
    context: .
    target: media-processor
  environment:
    - AWS_REGION=us-east-1
    - S3_BUCKET_NAME=court-case-media
    - REDIS_URL=redis://redis:6379
  volumes:
    - media_storage:/app/media
    # Remove this line - services are already in the image:
    # - ./backend/services:/app/services  # ❌ DELETE THIS
  depends_on:
    - redis
    - backend
```

#### Critical Issue 3: Media Processor Dockerfile Missing Dependencies

**Issue**: Media processor stage doesn't copy required core modules

```dockerfile
FROM python:3.11-slim AS media-processor

WORKDIR /app

COPY requirements-media.txt .
RUN pip install --no-cache-dir -r requirements-media.txt

COPY backend/services/media_service.py ./
COPY backend/core/ ./core/        # ✅ Copies core

CMD ["python", "-m", "services.media_service"]  # ❌ But runs as module
```

**Problem**:

1. Copies `media_service.py` to `/app/media_service.py`
2. Copies `core/` to `/app/core/`
3. But tries to run `python -m services.media_service`
4. This expects `/app/services/media_service.py` (doesn't exist!)

**Fix**:

```dockerfile
FROM python:3.11-slim AS media-processor

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install FFmpeg and media processing tools
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libavcodec-extra \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python media processing dependencies
COPY requirements-media.txt .
RUN pip install --no-cache-dir -r requirements-media.txt

# Copy required modules maintaining structure
COPY backend/services/ ./services/
COPY backend/core/ ./core/
COPY backend/__init__.py ./

# Create __init__.py files if missing
RUN touch ./services/__init__.py ./core/__init__.py

CMD ["python", "-m", "services.media_service"]
```

### ⚠️ WARNINGS

#### Warning 1: LocalStack Configuration Issues

**Issue**: LocalStack configuration may not work correctly

```yaml
localstack:
  environment:
    - DOCKER_HOST=unix:///var/run/docker.sock
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
```

**Impact**: LocalStack needs Docker socket access, which may not work in all environments

**Recommendation**: Add documentation about LocalStack requirements

#### Warning 2: No Resource Limits

**Issue**: No CPU/memory limits defined for services

```yaml
backend:
  # Missing:
  # deploy:
  #   resources:
  #     limits:
  #       cpus: '1.0'
  #       memory: 1G
```

**Impact**: Services can consume all host resources

**Recommendation**: Add resource limits

```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: "1.0"
        memory: 1G
      reservations:
        cpus: "0.5"
        memory: 512M
```

---

## 3. Dockerfile Analysis (`caseapp/Dockerfile`)

### ✅ CORRECT Configurations

1. **Multi-stage build** - Efficient image sizes ✅
2. **Non-root user** - Security best practice ✅
3. **Health check** - Proper health check defined ✅
4. **Layer optimization** - Dependencies installed before code copy ✅
5. **Environment variables** - Proper Python configuration ✅

### 🔴 CRITICAL ISSUES

#### Critical Issue 1: WORKDIR and COPY Mismatch

**Issue**: Backend code structure doesn't match expected runtime structure

```dockerfile
WORKDIR /app

# Copies backend/ contents to /app root
COPY backend/ ./

# Result: /app/main.py, /app/core/, /app/services/
# Expected by CMD: /app/main.py ✅ CORRECT
```

**Analysis**: This is actually CORRECT for the backend service!

**However**, the media-processor has issues (see Critical Issue 3 in docker-compose section).

#### Critical Issue 2: Missing **init**.py Files in COPY

**Issue**: The fix we applied (adding `__init__.py` files) isn't reflected in Dockerfile

```dockerfile
# Current Dockerfile doesn't ensure __init__.py exists
COPY backend/ ./

# Should explicitly create or verify __init__.py files
```

**Fix**:

```dockerfile
# Copy backend code to the app root (not in a subdirectory)
COPY backend/ ./

# Ensure __init__.py files exist (critical for Python imports)
RUN touch ./services/__init__.py ./core/__init__.py || true
```

#### Critical Issue 3: Frontend Stage is Minimal Placeholder

**Issue**: Frontend stage creates a placeholder HTML file instead of building real frontend

```dockerfile
FROM nginx:alpine AS frontend

# Create a minimal frontend
RUN echo '<!DOCTYPE html>' > /usr/share/nginx/html/index.html && \
    echo '<html><head><title>Court Case Management</title></head>' >> /usr/share/nginx/html/index.html
```

**Impact**: No real frontend is deployed

**Recommendation**: Either:

1. Build real frontend from `caseapp/frontend/` directory
2. Or document that frontend is placeholder-only

```dockerfile
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Copy frontend package files
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend source
COPY frontend/ ./
RUN npm run build

# Production stage
FROM nginx:alpine AS frontend

COPY --from=frontend-builder /app/dist /usr/share/nginx/html
COPY nginx/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
```

### ⚠️ WARNINGS

#### Warning 1: Shared Directory Not Copied

**Issue**: Dockerfile doesn't copy `shared/` directory

```dockerfile
COPY backend/ ./

# Missing:
# COPY shared/ ./shared/
```

**Impact**: If backend code imports from `shared/`, it will fail

**Fix**:

```dockerfile
# Copy backend code
COPY backend/ ./

# Copy shared code if it exists
COPY shared/ ./shared/ 2>/dev/null || true
```

#### Warning 2: Media Processor Missing Core Dependencies

**Issue**: Media processor copies `core/` but may need other modules

```dockerfile
COPY backend/services/media_service.py ./
COPY backend/core/ ./core/
# Missing: models/, schemas/, other dependencies
```

**Recommendation**: Copy all required modules or copy entire backend

```dockerfile
# Option 1: Copy specific modules
COPY backend/services/ ./services/
COPY backend/core/ ./core/
COPY backend/models/ ./models/
COPY backend/schemas/ ./schemas/

# Option 2: Copy entire backend (simpler, slightly larger)
COPY backend/ ./
```

---

## 4. Path and Directory Structure Issues

### Issue Summary: `/caseapp` Directory Confusion

**Repository Structure**:

```
/
├── .github/workflows/ci-cd.yml          # Root level
├── caseapp/                             # Application root
│   ├── backend/                         # Backend code
│   │   ├── main.py
│   │   ├── core/
│   │   ├── services/
│   │   └── __init__.py (ADDED)
│   ├── frontend/                        # Frontend code
│   ├── infrastructure/                  # CDK code
│   ├── shared/                          # Shared code
│   ├── Dockerfile                       # Docker build
│   ├── docker-compose.yml               # Local dev
│   └── requirements.txt                 # Dependencies
```

### Path Reference Matrix

| File                                      | Current Path | Correct? | Notes               |
| ----------------------------------------- | ------------ | -------- | ------------------- |
| **ci-cd.yml**                             |
| `pip install -r caseapp/requirements.txt` | ✅           | Correct  | From repo root      |
| `working-directory: caseapp/backend`      | ✅           | Correct  | From repo root      |
| `context: ./caseapp`                      | ✅           | Correct  | From repo root      |
| `file: ./caseapp/Dockerfile`              | ✅           | Correct  | From repo root      |
| **docker-compose.yml**                    |
| `context: .`                              | ✅           | Correct  | From /caseapp       |
| `- ./backend:/app`                        | ✅           | Correct  | From /caseapp       |
| `- ./shared:/app/shared`                  | ✅           | Correct  | From /caseapp       |
| **Dockerfile**                            |
| `COPY backend/ ./`                        | ✅           | Correct  | Context is /caseapp |
| `COPY shared/ ./shared/`                  | ⚠️           | Missing  | Should be added     |

### Recommendations

1. **Standardize path prefixes** in ci-cd.yml (use `./` consistently)
2. **Add shared/ copy** to Dockerfile if needed
3. **Fix media-processor** structure in Dockerfile
4. **Remove volume mount** for services in docker-compose.yml media-processor
5. **Add **init**.py creation** to Dockerfile explicitly

---

## 5. Comprehensive Fix Summary

### Priority 1: Critical Fixes (Must Fix Before Deployment)

1. **Fix media-processor Dockerfile structure**

   ```dockerfile
   COPY backend/services/ ./services/
   COPY backend/core/ ./core/
   RUN touch ./services/__init__.py ./core/__init__.py
   ```

2. **Remove conflicting volume mount in docker-compose.yml**

   ```yaml
   media-processor:
     volumes:
       - media_storage:/app/media
       # DELETE: - ./backend/services:/app/services
   ```

3. **Add **init**.py creation to backend Dockerfile**
   ```dockerfile
   COPY backend/ ./
   RUN touch ./services/__init__.py ./core/__init__.py || true
   ```

### Priority 2: Important Improvements

4. **Add validation step to workflow**
5. **Add health check validation to deployment**
6. **Standardize path prefixes in workflow**
7. **Add resource limits to docker-compose**

### Priority 3: Nice to Have

8. **Build real frontend** (currently placeholder)
9. **Add rollback strategy** to workflow
10. **Add LocalStack documentation**

---

## 6. Testing Recommendations

### Before Deployment

1. **Test Docker build locally**:

   ```bash
   cd caseapp
   docker build -t test-backend --target backend-base .
   docker build -t test-media --target media-processor .
   ```

2. **Test docker-compose locally**:

   ```bash
   cd caseapp
   docker-compose up --build
   docker-compose ps
   docker-compose logs backend
   ```

3. **Verify imports work**:

   ```bash
   docker-compose exec backend python -c "from core.config import settings; print('OK')"
   docker-compose exec backend python -c "from services.case_service import CaseService; print('OK')"
   ```

4. **Test health checks**:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/health/ready
   ```

### After Deployment

1. **Verify ECS tasks start successfully**
2. **Check CloudWatch logs for import errors**
3. **Verify health checks pass**
4. **Test API endpoints**

---

## 7. Conclusion

**Overall Assessment**: The configuration is mostly correct, but has several critical issues that need fixing before deployment #78.

**Key Findings**:

- ✅ Path references are generally correct for `/caseapp` structure
- 🔴 Media processor Dockerfile has structural issues
- 🔴 Missing `__init__.py` file creation in Dockerfile
- ⚠️ Several workflow improvements needed

**Next Steps**:

1. Apply Priority 1 fixes immediately
2. Test locally with docker-compose
3. Verify all imports work
4. Then proceed with deployment #78

**Estimated Fix Time**: 15-20 minutes for Priority 1 fixes
