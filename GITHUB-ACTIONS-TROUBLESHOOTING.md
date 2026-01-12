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

## Solution Implementation - Version 2

### Analysis of First Attempt

**Run ID**: 20933604287  
**Result**: Still failed after 3 minutes  
**Insight**: The issue is more fundamental than just timeout values - services need more time to initialize in GitHub Actions environment.

### Enhanced Solution (Current)

**Service Health Check Improvements**:

- **PostgreSQL**: Extended start period to 60 seconds, increased retries to 20, 3s intervals
- **Redis**: Extended start period to 30 seconds, increased retries to 20, 3s intervals
- **Rationale**: GitHub Actions runners may have variable performance affecting service startup

**Service Readiness Check Enhancements**:

- Extended timeout to 5 minutes (from 3 minutes)
- Increased retry attempts to 15 (from 10)
- Added debugging output for failed services (container logs, process status)
- Implemented connection testing beyond basic readiness checks
- Added exponential backoff with maximum delay cap (10 seconds)

**New Debugging Features**:

```bash
# Container log output for failed services
docker logs $(docker ps -q --filter ancestor=postgres:15)
docker logs $(docker ps -q --filter ancestor=redis:7-alpine)

# Process status checking
ps aux | grep postgres
ps aux | grep redis

# Connection testing
psql -h localhost -p 5432 -U postgres -d test_db -c 'SELECT 1;'
redis-cli -h localhost -p 6379 set test_key test_value
```

### Expected Outcome

With these enhanced configurations:

- Services should have sufficient time to initialize (60s for PostgreSQL, 30s for Redis)
- More frequent health checks (3s intervals) for faster detection
- Extended overall timeout (5 minutes) to accommodate slower GitHub Actions runners
- Comprehensive debugging if services still fail to start

### Monitoring Next Run

The next workflow run should provide detailed diagnostic information if services still fail, allowing us to identify the root cause and implement targeted fixes.
