# Deployment #95 Root Cause Analysis and Fix

**Date**: January 16, 2026  
**Deployment**: #95  
**Duration**: 54 minutes (cancelled before timeout)  
**Status**: Cancelled - Root cause identified and fixed

## Executive Summary

Deployment #95 exhibited the same failure pattern as deployment #89: the media processing service continuously cycled (0/1 tasks running) while the backend service remained healthy (2/2 tasks). Root cause analysis revealed the media processor was missing critical database configuration, causing it to attempt connections to localhost instead of the RDS instance.

## Failure Pattern

### Timeline

- **11:32 CST**: Deployment started (Run ID: 21075198152)
- **11:47 CST**: CloudFormation CREATE_IN_PROGRESS, media processor cycling begins
- **12:07 CST**: Backend service healthy (2/2), media processor still cycling (0/1)
- **12:26 CST**: Deployment cancelled after 54 minutes

### Service Status

- ✅ **Backend Service**: Healthy (2/2 tasks running consistently)
- ❌ **Media Processing Service**: Cycling (0/1 tasks, continuous restarts)
- ⏱️ **Pattern**: Same as deployment #89 which timed out at 60 minutes

## Root Cause Analysis

### Investigation Steps

1. **Checked stopped task reasons**:

   ```bash
   aws ecs describe-tasks --cluster <cluster> --tasks <task-arn>
   ```

   Result: `Essential container in task exited` with exit code 1

2. **Examined CloudWatch logs**:

   ```bash
   aws logs get-log-events --log-group-name <media-processor-log-group>
   ```

   Result: `ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 5432)`

3. **Compared infrastructure configurations**:
   - Backend service: Has database secrets (DB_HOST, DB_USER, DB_PASSWORD, DB_PORT, DB_NAME)
   - Media processor: Missing all database configuration

### Root Cause

**The media processing service was missing database connection configuration.**

The media processor container was configured with only:

- `AWS_REGION`
- `S3_BUCKET_NAME`

But it needed:

- Database secrets (DB_HOST, DB_USER, DB_PASSWORD, DB_PORT, DB_NAME)
- Redis URL
- Permission to read database secrets

Without `DB_HOST`, the application defaulted to `127.0.0.1:5432` (localhost), which doesn't exist in the container, causing immediate connection failures and continuous restarts.

## The Fix

### Changes Applied to `caseapp/infrastructure/app.py`

#### 1. Added Database Secret Permission (Line 869)

```python
# Grant permissions
self.media_bucket.grant_read_write(media_task_def.task_role)
self.database.secret.grant_read(media_task_def.task_role)  # ← ADDED
```

#### 2. Added Database Secrets to Container (Lines 876-891)

```python
media_container = media_task_def.add_container(
    "MediaProcessor",
    image=ecs.ContainerImage.from_registry(f"{docker_username}/court-case-media:latest"),
    environment={
        "AWS_REGION": self.region,
        "S3_BUCKET_NAME": self.media_bucket.bucket_name,
        "S3_MEDIA_BUCKET": self.media_bucket.bucket_name,  # ← ADDED
        "REDIS_URL": f"redis://{self.redis_cluster.attr_redis_endpoint_address}:6379"  # ← ADDED
    },
    secrets={  # ← ENTIRE SECTION ADDED
        # Use individual secret fields from RDS-generated secret
        "DB_HOST": ecs.Secret.from_secrets_manager(self.database.secret, "host"),
        "DB_USER": ecs.Secret.from_secrets_manager(self.database.secret, "username"),
        "DB_PASSWORD": ecs.Secret.from_secrets_manager(self.database.secret, "password"),
        "DB_PORT": ecs.Secret.from_secrets_manager(self.database.secret, "port"),
        "DB_NAME": ecs.Secret.from_secrets_manager(self.database.secret, "dbname")
    },
    logging=ecs.LogDrivers.aws_logs(
        stream_prefix="media-processor",
        log_retention=logs.RetentionDays.ONE_WEEK
    )
)
```

#### 3. Added Circuit Breaker (Lines 905-910)

```python
self.media_service = ecs.FargateService(
    self, "MediaProcessingService",
    cluster=self.cluster,
    task_definition=media_task_def,
    desired_count=1,
    circuit_breaker=ecs.DeploymentCircuitBreaker(  # ← ADDED
        rollback=True,
        enable=True  # Explicitly enable circuit breaker for automatic rollback
    )
)
```

## What Was Added

### Environment Variables

- `S3_MEDIA_BUCKET`: Media bucket name (consistency with backend)
- `REDIS_URL`: Redis connection string for caching

### Secrets (from AWS Secrets Manager)

- `DB_HOST`: RDS endpoint hostname
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password
- `DB_PORT`: Database port (5432)
- `DB_NAME`: Database name

### IAM Permissions

- `self.database.secret.grant_read(media_task_def.task_role)`: Permission to read database secrets

### Deployment Configuration

- Circuit breaker with automatic rollback on failures

## Why This Matters

### Before Fix

1. Media processor starts
2. Tries to connect to PostgreSQL at `127.0.0.1:5432`
3. Connection refused (localhost doesn't exist)
4. Container exits with code 1
5. ECS restarts the task
6. Cycle repeats indefinitely
7. Deployment times out after 60 minutes

### After Fix

1. Media processor starts
2. Reads DB_HOST from secrets (RDS endpoint)
3. Connects to actual RDS instance
4. Container stays running
5. Service becomes healthy
6. Deployment succeeds

## Comparison with Deployment #94

Deployment #94 (minimal backend-only) succeeded because:

- It only deployed the backend service
- Backend service had all database configuration
- No media processor to fail

Deployment #95 failed because:

- It deployed the full application including media processor
- Media processor was missing database configuration
- Same pattern as deployment #89

## Next Steps

1. ✅ **Fix Applied**: Database secrets added to media processor
2. ⏳ **Ready to Deploy**: Configuration now matches successful backend pattern
3. 🎯 **Expected Result**: Both services should start and stay healthy

## Lessons Learned

1. **Configuration Parity**: All services that need database access must have the same database configuration
2. **Early Log Checking**: CloudWatch logs immediately showed the connection error
3. **Pattern Recognition**: Same cycling pattern (0/1 tasks) = same root cause
4. **Systematic Debugging**: Check stopped task reasons → Check logs → Compare configurations

## Files Modified

- `caseapp/infrastructure/app.py` (Lines 869, 876-891, 905-910)

## Related Documentation

- `docs-archive/DEPLOYMENT-94-SUCCESS.md` - Successful minimal deployment reference
- `docs-archive/DEPLOYMENT-FIXES-APPLIED.md` - Previous fixes applied to full app
- `logs-archive/deployment-89-monitor.log` - Previous failure with same pattern
- `deployment-95-monitor.log` - Current deployment monitoring log
