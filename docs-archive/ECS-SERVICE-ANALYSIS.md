# ECS Service Configuration Analysis - Task 1.1

## Current Configuration Analysis

Based on the infrastructure code review (`caseapp/infrastructure/app.py`), I've identified several critical issues with the current ECS service configuration that are causing deployment failures:

### 1. **Memory Allocation Issue** ⚠️

**Current Configuration:**

```python
memory_limit_mib=2048,  # Only 2GB memory
cpu=1024,               # 1 vCPU
```

**Problem:** The current memory allocation of 2048 MiB (2GB) is insufficient for a complex FastAPI application with multiple dependencies, AI services, and database connections.

**Evidence from Requirements:** Requirement 2.1 states "minimum 4096 MiB for complex applications"

### 2. **Port Binding Configuration** ✅

**Current Configuration:**

```python
container_port=8000,
```

**Application Configuration (main.py):**

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # ✅ Correctly binds to all interfaces
        port=8000,
        reload=True,
        log_config=None
    )
```

**Status:** Port binding appears correct - application binds to 0.0.0.0:8000

### 3. **Health Check Configuration** ⚠️

**Current Issues:**

- No Docker HEALTHCHECK instruction in Dockerfile
- Basic health check endpoint exists (`/health`) but may not be comprehensive enough
- No ECS-specific health check configuration with appropriate timeouts

**Current Health Check Endpoint:**

```python
@app.get("/health")
async def health_check():
    # Basic health check that tests database and redis connectivity
```

### 4. **Container Startup Dependencies** ⚠️

**Identified Issues:**

- Application tries to connect to database, Redis, and AWS services on startup
- No graceful handling of service unavailability during container startup
- Complex service initialization in `ServiceManager` may cause startup timeouts

### 5. **Resource Constraints Analysis**

**Current ECS Service Configuration:**

```python
self.backend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
    self, "BackendService",
    cluster=self.cluster,
    memory_limit_mib=2048,  # ❌ Too low
    cpu=1024,               # ❌ May be too low
    desired_count=2,        # ✅ Good for redundancy
    # ... health check grace period not specified
)
```

**Missing Configuration:**

- No `health_check_grace_period` specified (defaults to 0)
- No deployment configuration for rolling updates
- No container-level health checks

### 6. **Application Startup Complexity**

**Service Manager Initialization:**
The application has a complex startup sequence that initializes multiple services:

- Database connections
- Redis connections
- AWS service clients (S3, RDS, OpenSearch, Cognito)
- AI service integrations (Bedrock, Textract, Comprehend)

This complex initialization may exceed the default ECS health check timeout.

### 7. **Docker Configuration Issues**

**Current Dockerfile:**

```dockerfile
# ❌ No HEALTHCHECK instruction
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Missing:**

- Docker HEALTHCHECK instruction
- Proper signal handling for graceful shutdown
- Startup readiness checks

## Root Cause Analysis

### Primary Issues:

1. **Insufficient Memory:** 2048 MiB is too low for the application complexity
2. **Missing Health Checks:** No Docker or ECS health check configuration
3. **Complex Startup:** Service initialization may timeout before health checks pass
4. **No Grace Period:** ECS immediately starts health checks without allowing startup time

### Secondary Issues:

1. **No Deployment Configuration:** Missing rolling update settings
2. **Resource Optimization:** CPU allocation may be insufficient
3. **Logging Configuration:** Limited to 1 week retention

## Recommended Fixes (Next Tasks)

### Immediate Fixes (Task 1.2-1.4):

1. **Increase Memory:** 2048 MiB → 4096 MiB
2. **Add Health Check Grace Period:** 300 seconds (5 minutes)
3. **Implement Docker HEALTHCHECK:** Add to Dockerfile
4. **Optimize Health Check Endpoint:** Make it more comprehensive
5. **Add ECS Health Check Configuration:** Proper timeout and retry settings

### Configuration Changes Needed:

```python
# Updated ECS configuration
memory_limit_mib=4096,  # Increase to 4GB
cpu=2048,               # Increase to 2 vCPU
health_check_grace_period_seconds=300,  # 5 minute grace period
```

## Current Status Summary

- ✅ **Port Binding:** Correctly configured (0.0.0.0:8000)
- ❌ **Memory Allocation:** Too low (2048 MiB vs required 4096 MiB)
- ❌ **Health Checks:** Missing Docker and ECS health check configuration
- ❌ **Startup Time:** No grace period for complex service initialization
- ⚠️ **Application Complexity:** Multiple service dependencies may cause startup delays

## Next Steps

Task 1.1 is complete. The analysis shows that the primary issues are:

1. Insufficient memory allocation
2. Missing health check configuration
3. No startup grace period

These issues align with Requirements 1.1, 1.3, 2.1, and 6.1 from the specification.

Ready to proceed to Task 1.2: Fix application port binding and health check configuration.
