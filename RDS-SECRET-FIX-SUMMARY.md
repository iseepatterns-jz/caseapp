# RDS Secret Configuration Fix - Summary

## Issue Identified

**Date**: 2026-01-14  
**Deployment Run**: #20979184945  
**Time to Identify**: T+45 minutes into deployment

### Problem

ECS tasks were failing to start with the error:

```
ResourceInitializationError: unable to retrieve secret from asm:
retrieved secret from Secrets Manager did not contain json key connectionString
```

### Root Cause

**CDK Infrastructure Bug**: The ECS task definition was trying to read a `connectionString` field from the RDS-generated Secrets Manager secret, but this field doesn't exist.

**What RDS Actually Provides**:

- `host` - Database endpoint
- `username` - Database user
- `password` - Database password
- `port` - Database port (5432)
- `dbname` - Database name
- `engine` - Database engine (postgres)
- `dbInstanceIdentifier` - RDS instance ID

**What CDK Was Requesting**:

- `connectionString` - **Does not exist**

### Impact

- **Deployment appeared to progress** but ECS service couldn't start tasks
- **0/2 tasks running** despite service being ACTIVE
- **Application completely unavailable** (no healthy targets)
- **Blocking issue** preventing any deployment from working

## Solution Implemented

### 1. CDK Infrastructure Changes (`caseapp/infrastructure/app.py`)

**Before**:

```python
secrets={
    "DATABASE_URL": ecs.Secret.from_secrets_manager(self.database.secret, "connectionString")
}
```

**After**:

```python
secrets={
    # Use individual secret fields from RDS-generated secret
    "DB_HOST": ecs.Secret.from_secrets_manager(self.database.secret, "host"),
    "DB_USER": ecs.Secret.from_secrets_manager(self.database.secret, "username"),
    "DB_PASSWORD": ecs.Secret.from_secrets_manager(self.database.secret, "password"),
    "DB_PORT": ecs.Secret.from_secrets_manager(self.database.secret, "port"),
    "DB_NAME": ecs.Secret.from_secrets_manager(self.database.secret, "dbname")
}
```

### 2. Backend Configuration Changes (`caseapp/backend/core/config.py`)

**Before**:

```python
DATABASE_URL: str = "postgresql://user:password@localhost/courtcase_db"
```

**After**:

```python
# Database - Individual components for RDS secret compatibility
DB_HOST: str = "localhost"
DB_PORT: str = "5432"
DB_USER: str = "user"
DB_PASSWORD: str = "password"
DB_NAME: str = "courtcase_db"

# Constructed DATABASE_URL from individual components
@property
def DATABASE_URL(self) -> str:
    """Construct PostgreSQL connection URL from individual components"""
    return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
```

**Key Design Decision**: Used a `@property` to maintain backward compatibility. All existing code using `settings.DATABASE_URL` continues to work without changes.

### 3. Docker Compose Changes (`caseapp/docker-compose.yml`)

**Before**:

```yaml
environment:
  - DATABASE_URL=postgresql://courtcase_user:courtcase_password@postgres:5432/courtcase_db
```

**After**:

```yaml
environment:
  # Database configuration (individual fields for RDS compatibility)
  - DB_HOST=postgres
  - DB_PORT=5432
  - DB_USER=courtcase_user
  - DB_PASSWORD=courtcase_password
  - DB_NAME=courtcase_db
```

### 4. Documentation Updates (`.env.example`)

Updated to reflect the new individual database field approach.

## Testing Performed

### 1. Syntax Validation

- ✅ CDK Python syntax check passed
- ✅ Backend config syntax check passed

### 2. Local Docker Testing

```bash
docker compose up --build backend
curl http://localhost:8000/health
```

**Result**:

```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

✅ **Database connection working with new configuration**

### 3. Deployment

- Committed changes with comprehensive commit message
- Pushed to main branch
- New deployment triggered: Run #20980650291

## Deployment Timeline

### Previous Deployment (Run #20979184945)

- **Started**: 2026-01-14 01:39 UTC
- **Status at Discovery**: T+45 minutes, still CREATE_IN_PROGRESS
- **Issue**: ECS service ACTIVE but 0/2 tasks running
- **RDS Database**: Available since 01:57 UTC
- **Problem**: Tasks failing to start due to secret key mismatch

### New Deployment (Run #20980650291)

- **Started**: 2026-01-14 02:56 UTC
- **Status**: In progress (test phase)
- **Expected Outcome**: ECS tasks should start successfully

## Key Learnings

### 1. RDS Secret Structure

- RDS automatically generates secrets with specific field names
- These fields are **not customizable**
- Must use the exact field names RDS provides

### 2. ECS Secret References

- `ecs.Secret.from_secrets_manager(secret, field)` requires exact field name
- No automatic field mapping or transformation
- Mismatch causes immediate task startup failure

### 3. Testing Strategy

- **Always test locally first** with docker-compose
- **Verify secret structure** in AWS Secrets Manager before deployment
- **Check ECS task events** for secret-related errors

### 4. Backward Compatibility

- Using `@property` in Pydantic settings maintains compatibility
- Existing code using `DATABASE_URL` continues to work
- No breaking changes to application logic

## Prevention Measures

### 1. Documentation

- Document RDS secret field names in infrastructure code
- Add comments explaining why individual fields are used

### 2. Validation

- Add CDK tests to verify secret field references
- Include secret structure validation in CI/CD

### 3. Monitoring

- Monitor ECS task startup failures
- Alert on 0 running tasks for extended periods
- Check CloudWatch logs for secret-related errors

## Related Files

- `caseapp/infrastructure/app.py` - CDK infrastructure
- `caseapp/backend/core/config.py` - Backend configuration
- `caseapp/docker-compose.yml` - Local development
- `caseapp/.env.example` - Environment variable documentation
- `ROOT-CAUSE-ANALYSIS.md` - Previous deployment issue analysis

## Next Steps

1. ✅ Monitor new deployment (Run #20980650291)
2. ⏳ Verify ECS tasks start successfully
3. ⏳ Confirm application health checks pass
4. ⏳ Validate database connectivity in production
5. ⏳ Update deployment documentation with this fix

## Commit Information

**Commit**: 3ceafcb  
**Message**: "fix: Use individual RDS secret fields instead of connectionString"  
**Files Changed**: 4  
**Insertions**: 31  
**Deletions**: 6

## Status

🔄 **IN PROGRESS** - New deployment running with fix applied  
⏰ **Next Check**: Monitor deployment progress every 5 minutes
