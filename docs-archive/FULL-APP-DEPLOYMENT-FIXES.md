# Full Application Deployment Fixes

**Date**: January 16, 2026  
**Purpose**: Apply learnings from successful minimal deployment (#94) to full application  
**Base Commit**: 82a7d5c0e83694e50c5269b13fe7c69ee80e40d6 (last full app state)  
**Reference Commit**: caf30b12a3651f5fee7d96e2415940a597d7616f (successful minimal deployment)

---

## Executive Summary

Deployment #94 successfully deployed a minimal backend after 5+ days of troubleshooting. The root causes were:

1. **PostgreSQL Version Mismatch**: CDK constants (VER_15_7, VER_15_8) don't exist in RDS
2. **Insufficient Resources**: 512MB memory too small for FastAPI + SQLAlchemy
3. **Health Check Timing**: 60-second start period too short for database-backed apps
4. **Health Check Dependencies**: ALB health checks requiring database caused task cycling

This document details the specific changes needed to apply these fixes to the full application.

---

## Critical Fixes Required

### 1. PostgreSQL Version Fix

**Problem**: CDK provides version constants that don't exist in RDS.

**Current Code** (app.py line ~200):

```python
engine=rds.DatabaseInstanceEngine.postgres(
    version=rds.PostgresEngineVersion.VER_15
)
```

**Fixed Code**:

```python
engine=rds.DatabaseInstanceEngine.postgres(
    version=rds.PostgresEngineVersion.of("15", "15.15")  # Latest available in RDS
)
```

**Why**:

- RDS only supports: 15.10, 15.12, 15.13, 15.14, 15.15
- CDK constants like VER_15_7, VER_15_8 don't exist in RDS
- Using `.of("15", "15.15")` ensures we use the latest available version

**Location**: `caseapp/infrastructure/app.py`, line ~200 in `create_database()` method

---

### 2. Resource Allocation Increase

**Problem**: 512MB memory insufficient for FastAPI + SQLAlchemy + all dependencies.

**Current Code** (app.py line ~450):

```python
memory_limit_mib=4096,  # Already increased to 4096
cpu=2048,               # Already increased to 2048
```

**Status**: ✅ **Already Fixed** - Full app already has sufficient resources

**Note**: The full app already has 4096MB memory and 2048 CPU, which is more than the minimal app's 1024MB/512 CPU. This is appropriate for the full application with all services.

---

### 3. Health Check Timing Configuration

**Problem**: 60-second start period too short for database connection + app startup.

**Current Code** (app.py line ~450):

```python
health_check_grace_period=Duration.seconds(300),  # 5 minute grace period for startup
```

**Status**: ✅ **Already Fixed** - Full app already has 300-second grace period

**Container Health Check** - Need to verify/add:

**Location to Check**: `caseapp/infrastructure/app.py`, in `create_ecs_cluster()` method

**Required Configuration**:

```python
# In backend task definition container
health_check=ecs.HealthCheck(
    command=["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
    interval=Duration.seconds(30),
    timeout=Duration.seconds(10),  # Increased from 5
    retries=3,
    start_period=Duration.seconds(180)  # 3 minutes for DB connection
)
```

**Action Required**:

- Check if container health check is defined in full app
- If not, add it to the backend container definition
- If exists, verify start_period is at least 180 seconds

---

### 4. Health Endpoint Strategy

**Problem**: ALB health check using database-dependent endpoint causes task cycling.

**Current Code** (app.py line ~600):

```python
# Configure load balancer health check
# Use root endpoint / which is simple and doesn't require database
self.backend_service.target_group.configure_health_check(
    path="/",                       # Use root endpoint (simple, no DB required)
    healthy_threshold_count=2,
    unhealthy_threshold_count=3,
    timeout=Duration.seconds(10),
    interval=Duration.seconds(30),
    port="8000"
)
```

**Status**: ✅ **Already Fixed** - Full app uses "/" endpoint

**Backend Health Endpoint** - Need to verify:

**Location**: `caseapp/backend/main.py`

**Required Endpoints**:

```python
@app.get("/health")
async def health_check():
    """Simple health check - no database required"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "backend",
        "version": "1.0.0"
    }

@app.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness check - includes database"""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database not ready: {str(e)}"
        )
```

**Action Required**:

- Verify `/health` endpoint exists and doesn't require database
- Verify `/health/ready` endpoint exists for comprehensive checks
- Ensure ALB uses `/health` (simple) not `/health/ready` (database-dependent)

---

## Additional Improvements from Minimal Deployment

### 5. Docker Hub Credentials Configuration

**Current Code** (app.py line ~550):

```python
# Add Docker Hub credentials to backend task definition
cfn_task_def = self.backend_service.task_definition.node.default_child
cfn_task_def.add_property_override(
    "ContainerDefinitions.0.RepositoryCredentials",
    {
        "CredentialsParameter": dockerhub_secret.secret_arn
    }
)
```

**Status**: ✅ **Already Implemented** - Full app has Docker Hub credentials

---

### 6. Circuit Breaker Configuration

**Problem**: No automatic rollback on repeated deployment failures.

**Current Code** (app.py line ~450):

```python
# Deployment configuration - use direct parameters instead of DeploymentConfiguration object
min_healthy_percent=50,     # Maintain at least 50% healthy tasks during deployment
max_healthy_percent=200,    # Allow up to 200% of desired capacity during deployment
```

**Missing**: Circuit breaker configuration

**Required Addition**:

```python
backend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
    self, "BackendService",
    cluster=self.cluster,
    # ... existing parameters ...
    circuit_breaker=ecs.DeploymentCircuitBreaker(
        rollback=True,
        enable=True  # Explicitly enable circuit breaker
    )
)
```

**Location**: `caseapp/infrastructure/app.py`, line ~450 in `create_ecs_cluster()` method

**Action Required**: Add circuit_breaker parameter to ApplicationLoadBalancedFargateService

---

## Implementation Checklist

### Critical Fixes (Must Apply)

- [ ] **Fix 1: PostgreSQL Version**

  - File: `caseapp/infrastructure/app.py`
  - Line: ~200 in `create_database()`
  - Change: `version=rds.PostgresEngineVersion.VER_15` → `version=rds.PostgresEngineVersion.of("15", "15.15")`

- [ ] **Fix 3: Container Health Check**

  - File: `caseapp/infrastructure/app.py`
  - Location: `create_ecs_cluster()` method, backend container definition
  - Action: Verify/add health_check with 180-second start_period

- [ ] **Fix 4: Health Endpoints**

  - File: `caseapp/backend/main.py`
  - Action: Verify `/health` endpoint exists and is simple (no DB)
  - Action: Verify `/health/ready` endpoint exists for comprehensive checks

- [ ] **Fix 6: Circuit Breaker**
  - File: `caseapp/infrastructure/app.py`
  - Line: ~450 in `create_ecs_cluster()`
  - Action: Add `circuit_breaker` parameter to backend service

### Already Fixed (Verify Only)

- [x] **Fix 2: Resource Allocation** - Already 4096MB/2048 CPU
- [x] **Fix 5: Docker Hub Credentials** - Already implemented
- [x] **ALB Health Check Path** - Already uses "/" endpoint
- [x] **ALB Grace Period** - Already 300 seconds

---

## Testing Strategy

### Phase 1: Local Verification

```bash
# 1. Verify health endpoints work locally
cd caseapp
docker-compose up --build

# 2. Test health endpoints
curl http://localhost:8000/health
curl http://localhost:8000/health/ready

# 3. Verify no database dependency on /health
# Stop database and test /health still works
docker-compose stop db
curl http://localhost:8000/health  # Should still return 200
curl http://localhost:8000/health/ready  # Should return 503
```

### Phase 2: CDK Validation

```bash
# 1. Synthesize template
cd caseapp/infrastructure
cdk synth > /tmp/full-app-template.yaml

# 2. Validate PostgreSQL version
grep -A 5 "PostgresEngineVersion" /tmp/full-app-template.yaml
# Should show: "15.15" not "15.7" or "15.8"

# 3. Validate health check timing
grep -A 10 "HealthCheck" /tmp/full-app-template.yaml
# Should show: StartPeriod: 180 seconds

# 4. Validate circuit breaker
grep -A 5 "CircuitBreaker" /tmp/full-app-template.yaml
# Should show: Enable: true, Rollback: true
```

### Phase 3: Deployment

```bash
# 1. Clean environment
cd caseapp/infrastructure
cdk destroy --all --force

# 2. Verify clean state
bash ../../verify-resources-before-deploy.sh

# 3. Deploy full application
cdk deploy CourtCaseManagementStack

# 4. Monitor deployment
# Use deployment-monitor.sh script
bash ../scripts/deployment-monitor.sh
```

---

## Expected Deployment Timeline

Based on minimal deployment success:

- **Stack Creation**: ~14 minutes
- **ECS Task Startup**: ~3 minutes after stack creation
- **Health Check Stabilization**: ~2 minutes
- **Total Time**: ~20 minutes

**Full Application** (with all services):

- **Estimated Total**: ~30-40 minutes
- **Critical Phase**: First 5 minutes (task startup)
- **Monitoring Required**: Every 5 minutes for first 20 minutes

---

## Monitoring Commands

```bash
# Watch stack status
watch -n 30 'AWS_PAGER="" aws cloudformation describe-stacks \
  --stack-name CourtCaseManagementStack \
  --region us-east-1 | jq -r ".Stacks[0].StackStatus"'

# Watch ECS service
watch -n 30 'AWS_PAGER="" aws ecs describe-services \
  --cluster <cluster-name> \
  --services <service-name> \
  --region us-east-1 | jq -r ".services[0] | {runningCount, desiredCount, status}"'

# Get stopped task reasons
AWS_PAGER="" aws ecs list-tasks \
  --cluster <cluster-name> \
  --desired-status STOPPED \
  --max-items 5 | jq -r '.taskArns[]' | while read task; do
    AWS_PAGER="" aws ecs describe-tasks \
      --cluster <cluster-name> \
      --tasks $task | jq -r '.tasks[0] | {stoppedReason, containers: [.containers[] | {name, exitCode, reason}]}'
done

# Get CloudWatch logs
AWS_PAGER="" aws logs tail /aws/ecs/<log-group> --follow --format short
```

---

## Rollback Plan

If deployment fails:

1. **Immediate Actions**:

   ```bash
   # Cancel deployment if in progress
   cdk destroy CourtCaseManagementStack --force

   # Verify clean state
   bash verify-resources-before-deploy.sh
   ```

2. **Investigate Failure**:

   ```bash
   # Get stack events
   AWS_PAGER="" aws cloudformation describe-stack-events \
     --stack-name CourtCaseManagementStack \
     --max-items 20

   # Get ECS task failures
   # (use commands above)
   ```

3. **Revert Changes**:

   ```bash
   # Revert to last working commit
   git checkout 82a7d5c0e83694e50c5269b13fe7c69ee80e40d6

   # Or revert specific file
   git checkout 82a7d5c0e83694e50c5269b13fe7c69ee80e40d6 -- infrastructure/app.py
   ```

---

## Success Criteria

Deployment is successful when:

1. ✅ CloudFormation stack reaches CREATE_COMPLETE
2. ✅ ECS service shows runningCount = desiredCount = 2
3. ✅ Tasks stay running for > 5 minutes without cycling
4. ✅ ALB health checks pass consistently
5. ✅ Load balancer DNS returns 200 OK from /health endpoint
6. ✅ Database connections work (test /health/ready)
7. ✅ All services (backend, media processor) are healthy

---

## Key Learnings Applied

### From Minimal Deployment Success

1. **PostgreSQL Version**: Use `.of("15", "15.15")` instead of CDK constants
2. **Resource Allocation**: 1024MB minimum for FastAPI + SQLAlchemy
3. **Health Check Timing**: 180-second start period for database-backed apps
4. **Health Endpoint Strategy**: Simple /health for ALB, comprehensive /health/ready for monitoring
5. **Circuit Breaker**: Enable automatic rollback on repeated failures

### From Previous Deployment Failures

1. **Docker Hub Credentials**: Use Secrets Manager with explicit execution role
2. **Enhanced Monitoring**: Disabled (missing IAM role causes failures)
3. **Security Groups**: Minimal required permissions only
4. **Deletion Protection**: Disabled for testing/development
5. **OpenSearch**: Temporarily disabled (adds 16+ minutes to deployment)

---

## Next Steps After Successful Deployment

1. **Verify All Services**:

   - Backend API responds
   - Database connections work
   - Media processor is running
   - Redis cache is accessible

2. **Enable Monitoring**:

   - CloudWatch dashboard
   - CloudWatch alarms
   - SNS notifications

3. **Test Application Features**:

   - User authentication
   - Document upload
   - Media processing
   - Search functionality

4. **Re-enable OpenSearch** (if needed):

   - Uncomment OpenSearch code
   - Deploy incremental update
   - Monitor for 16+ minutes

5. **Production Hardening**:
   - Enable deletion protection
   - Enable enhanced monitoring
   - Configure auto-scaling
   - Set up backup policies

---

## References

- **Successful Minimal Deployment**: DEPLOYMENT-94-SUCCESS.md
- **Minimal Deployment Strategy**: MINIMAL-DEPLOYMENT-STRATEGY.md
- **Last Full App Commit**: 82a7d5c0e83694e50c5269b13fe7c69ee80e40d6
- **Successful Minimal Commit**: caf30b12a3651f5fee7d96e2415940a597d7616f

---

**Status**: Ready for Implementation  
**Risk Level**: Low (fixes are proven in minimal deployment)  
**Estimated Time**: 2-3 hours (implementation + testing + deployment)  
**Next Action**: Apply fixes to app.py and verify health endpoints
