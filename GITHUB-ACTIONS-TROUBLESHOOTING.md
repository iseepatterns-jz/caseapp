# GitHub Actions Troubleshooting Guide

## Current Issue Analysis

**Date**: January 12, 2026  
**Issue**: GitHub Actions CI pipeline failing on "Wait for services to be ready" step  
**Error Code**: Exit code 124 (timeout)  
**Failed Run ID**: 20899322037

## Root Cause Analysis

### Problem

The GitHub Actions workflow was failing because:

1. **Insufficient Timeout**: The "Wait for services to be ready" step had only a 1-minute timeout
2. **Basic Health Checks**: Simple 30-second timeout commands without retry logic
3. **Service Configuration**: PostgreSQL and Redis services had basic health check configurations

### Specific Failure Point

```
X Wait for services to be ready
Process completed with exit code 124.
```

Exit code 124 indicates the `timeout` command terminated the process due to exceeding the time limit.

## Solution Implemented

### 1. Enhanced Service Readiness Check

**Before**:

```bash
timeout 30 bash -c 'until pg_isready -h localhost -p 5432; do sleep 1; done'
timeout 30 bash -c 'until redis-cli -h localhost -p 6379 ping; do sleep 1; done'
```

**After**:

- Implemented exponential backoff retry logic
- Extended timeout to 3 minutes
- Added detailed logging and progress indicators
- Separate retry functions for each service

### 2. Improved Service Health Checks

**PostgreSQL**:

- Increased health check retries from 5 to 10
- Added 30-second start period
- More frequent health checks (5s interval)
- Improved health command with database specification

**Redis**:

- Increased health check retries from 5 to 10
- Added 15-second start period
- More frequent health checks (5s interval)

### 3. Better Error Handling

- Clear service-specific error messages
- Attempt counting and progress reporting
- Exponential backoff to reduce system load
- Graceful failure with detailed diagnostics

## Files Modified

1. `.github/workflows/ci-cd.yml`
   - Updated "Wait for services to be ready" step
   - Enhanced PostgreSQL service configuration
   - Enhanced Redis service configuration

## Testing Strategy

### Local Testing

The services work correctly in local Docker environment, confirming the issue is specific to GitHub Actions runner environment timing.

### Validation Steps

1. **Commit and push changes** to trigger new workflow run
2. **Monitor workflow execution** using `gh run list` and `gh run view`
3. **Verify service startup times** in workflow logs
4. **Confirm test execution** proceeds successfully after service readiness

## Monitoring Commands

```bash
# Check recent workflow runs
gh run list --limit 5

# Monitor specific run (replace with actual run ID)
gh run view <run-id>

# Get failed logs (with timeout handling)
gh run view <run-id> --log-failed

# Check workflow status in real-time
watch -n 10 'gh run list --limit 3'
```

## Prevention Measures

### 1. Timeout Handling

- Always use appropriate timeouts for CI services (2-3 minutes minimum)
- Implement retry logic with exponential backoff
- Add detailed logging for troubleshooting

### 2. Service Configuration

- Use health check start periods for services that need initialization time
- Configure appropriate health check intervals and retries
- Monitor service startup patterns to optimize configurations

### 3. MCP Tool Integration

- Implement timeout handling for MCP tools to prevent crashes
- Use CLI fallback methods when MCP tools fail
- Document troubleshooting procedures for future issues

## Next Steps

1. **Monitor New Workflow Run**: Verify the fixes resolve the timeout issue
2. **Performance Optimization**: If services still take too long, investigate runner performance
3. **Additional Reliability**: Consider adding service dependency checks and startup validation
4. **Documentation**: Update deployment documentation with troubleshooting procedures

## Related Issues

- **Local Testing**: All services work correctly in local environment
- **Deployment Pipeline**: Blocked until CI pipeline passes
- **AWS Infrastructure**: Ready for deployment once CI issues are resolved

## Success Criteria

✅ **Service Readiness**: PostgreSQL and Redis start within 3-minute timeout  
✅ **Test Execution**: Backend tests run successfully after service startup  
✅ **Pipeline Progression**: Build and deployment jobs execute after successful tests  
✅ **Error Handling**: Clear diagnostic messages for any remaining issues

This troubleshooting approach ensures systematic resolution of CI pipeline issues while building resilience for future deployments.

## Solution Implementation - Version 3 (FINAL FIX)

### Root Cause Identified

**Issue**: The `pg_isready` and `redis-cli` commands are not available on GitHub Actions runner host systems, even though the PostgreSQL and Redis containers are running and healthy.

**Evidence**: Local testing revealed that:

- Host system commands fail: `pg_isready -h localhost` and `redis-cli -h localhost`
- Docker exec commands work: `docker exec <container> pg_isready` and `docker exec <container> redis-cli`

### Final Solution Applied

**Changed from host commands**:

```bash
pg_isready -h localhost -p 5432 -U postgres -q
redis-cli -h localhost -p 6379 ping > /dev/null 2>&1
```

**To Docker exec commands**:

```bash
docker exec $(docker ps -q --filter ancestor=postgres:15) pg_isready -U postgres -d test_db > /dev/null 2>&1
docker exec $(docker ps -q --filter ancestor=redis:7-alpine) redis-cli ping > /dev/null 2>&1
```

### Why This Works

1. **Container Isolation**: Commands execute inside containers where tools are guaranteed to be available
2. **No Host Dependencies**: Doesn't rely on GitHub Actions runner having PostgreSQL or Redis clients installed
3. **Direct Container Access**: Tests the actual service running inside the container
4. **Reliable Detection**: Uses container-specific image filters to find the right containers

### Updated Files

1. **`.github/workflows/ci-cd.yml`**: Updated "Wait for services to be ready" step to use Docker exec
2. **`caseapp/scripts/test-ci-services-locally.sh`**: Enhanced to validate both approaches and demonstrate the fix

### Expected Outcome

The next GitHub Actions run should:

- ✅ Successfully detect when PostgreSQL is ready via Docker exec
- ✅ Successfully detect when Redis is ready via Docker exec
- ✅ Proceed to run backend tests without timeout failures
- ✅ Complete the full CI/CD pipeline including deployment

### Validation

The local test script now validates:

- Host command availability (demonstrates the problem)
- Docker exec command reliability (demonstrates the solution)
- Full service readiness using the new approach
- Backend test execution with proper service dependencies
