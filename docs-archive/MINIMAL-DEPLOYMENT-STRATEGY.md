# Minimal Deployment Strategy - ECS Task Cycling Root Cause Analysis

## Current Situation

**Deployment #89 Failed**: Backend service cycling (0/2 → 2/2 → 4/2 → 2/2) for ~90 minutes before CloudFormation timeout.

**Error Pattern**: "Essential container in task exited" - tasks starting then immediately stopping.

## Root Cause Analysis from AWS Documentation

Based on AWS Powers search results, the most common causes for ECS task cycling are:

### 1. Container Health Check Failures (MOST LIKELY)

**Symptoms**: Tasks start, health checks fail, tasks stop and restart
**From AWS Docs**: "Container health checks failing" is the #1 cause of service instability

**Our Configuration Issues**:

```python
# Current health check in minimal_app.py
health_check=ecs.HealthCheck(
    command=["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
    interval=Duration.seconds(30),
    timeout=Duration.seconds(5),
    retries=3,
    start_period=Duration.seconds(60)  # Only 60 seconds!
)
```

**Problems**:

- ✅ `curl` is installed in Dockerfile
- ❌ **60-second start_period is TOO SHORT** for FastAPI app with database connection
- ❌ **No verification that /health endpoint exists and works**
- ❌ **Database connection may be timing out**

### 2. Application Startup Issues

**Symptoms**: Container exits immediately with exit code 0 or 1
**From AWS Docs**: "Amazon ECS tasks exiting with non-zero exit codes"

**Potential Issues**:

- Database connection failures (RDS not ready)
- Missing environment variables
- Import errors (we fixed aws_service.py but may have others)
- Application crashes during startup

### 3. Memory/Resource Constraints

**Symptoms**: Tasks stop unexpectedly, OOMKilled errors
**From AWS Docs**: "Memory issues can cause containers to exit"

**Our Configuration**:

```python
memory_limit_mib=512,  # Only 512MB
cpu=256,  # Only 256 CPU units
```

**Risk**: FastAPI + SQLAlchemy + all dependencies may exceed 512MB during startup

### 4. Load Balancer Health Check Failures

**Symptoms**: Tasks deregistered from target group
**From AWS Docs**: "ELB health checks failing" causes task cycling

**Our Configuration**:

```python
# ALB health check
backend_service.target_group.configure_health_check(
    path="/health",
    interval=Duration.seconds(30),
    timeout=Duration.seconds(5),
    healthy_threshold_count=2,
    unhealthy_threshold_count=3
)
```

**Problems**:

- ❌ **No grace period configured** - ALB starts checking immediately
- ❌ **Only 120-second grace period** in service definition (too short)
- ❌ **Health check may start before app is ready**

## AWS Best Practices from Documentation

### Health Check Configuration (Critical)

**From AWS CDK Patterns**:

```python
# RECOMMENDED: Longer start period for database-backed apps
health_check=ecs.HealthCheck(
    command=["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
    interval=Duration.seconds(30),
    timeout=Duration.seconds(10),  # Increased timeout
    retries=3,
    start_period=Duration.seconds(180)  # 3 minutes for DB connection
)

# RECOMMENDED: Longer ALB grace period
health_check_grace_period=Duration.seconds(300)  # 5 minutes
```

### Resource Allocation

**From AWS Docs**: "Allocating more memory in the task definition can resolve container exits"

**Recommended Minimal Configuration**:

```python
memory_limit_mib=1024,  # Double to 1GB
cpu=512,  # Double to 512 CPU units
```

### Deployment Configuration

**From AWS Solutions Constructs**:

```python
deployment_configuration=ecs.DeploymentConfiguration(
    maximum_percent=150,
    minimum_healthy_percent=75  # Allow some unhealthy during deployment
)
```

## Recommended Minimal Stack Changes

### 1. Increase Health Check Timeouts

```python
# Container health check
health_check=ecs.HealthCheck(
    command=["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
    interval=Duration.seconds(30),
    timeout=Duration.seconds(10),  # Increased from 5
    retries=3,
    start_period=Duration.seconds(180)  # Increased from 60
)

# Service grace period
health_check_grace_period=Duration.seconds(300)  # Increased from 120
```

### 2. Increase Resource Allocation

```python
backend_task = ecs.FargateTaskDefinition(
    self, "BackendTask",
    memory_limit_mib=1024,  # Increased from 512
    cpu=512,  # Increased from 256
)
```

### 3. Add Deployment Circuit Breaker

```python
backend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
    self, "BackendService",
    cluster=cluster,
    task_definition=backend_task,
    desired_count=1,
    public_load_balancer=True,
    health_check_grace_period=Duration.seconds(300),
    circuit_breaker=ecs.DeploymentCircuitBreaker(
        rollback=True,
        enable=True  # Explicitly enable
    )
)
```

### 4. Simplify Health Check Endpoint

**Create a simple health endpoint that doesn't require database**:

```python
# In backend/main.py
@app.get("/health")
async def health_check():
    """Simple health check - no database required"""
    return {"status": "healthy", "service": "backend"}

@app.get("/health/ready")
async def readiness_check():
    """Readiness check - includes database"""
    try:
        # Test database connection
        db = next(get_db())
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database not ready: {str(e)}")
```

**Use simple /health for container health check, /health/ready for ALB**:

```python
# Container health check - simple, no DB
health_check=ecs.HealthCheck(
    command=["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
    ...
)

# ALB health check - includes DB readiness
backend_service.target_group.configure_health_check(
    path="/health/ready",  # More comprehensive check
    ...
)
```

## Testing Strategy

### Phase 1: Local Docker Testing

```bash
# Build and run locally
cd caseapp
docker build -t test-backend --target backend-base .
docker run -p 8000:8000 -e DATABASE_URL=postgresql://user:pass@host:5432/db test-backend

# Test health endpoints
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

### Phase 2: Minimal CDK Deployment

1. Apply all recommended changes to `minimal_app.py`
2. Synthesize and validate: `cdk synth -a "python minimal_app.py"`
3. Deploy with monitoring: `cdk deploy MinimalBackendStack`
4. Monitor CloudWatch logs immediately
5. Check ECS task status every 30 seconds

### Phase 3: Incremental Addition

Once minimal backend is stable:

1. Add Redis (if needed)
2. Add media processor (if needed)
3. Add other services one at a time

## Monitoring Commands

```bash
# Watch stack status
watch -n 10 'AWS_PAGER="" aws cloudformation describe-stacks --stack-name MinimalBackendStack --region us-east-1 | jq -r ".Stacks[0].StackStatus"'

# Watch ECS service
watch -n 10 'AWS_PAGER="" aws ecs describe-services --cluster <cluster-name> --services <service-name> --region us-east-1 | jq -r ".services[0] | {runningCount, desiredCount, status}"'

# Get stopped task reasons
AWS_PAGER="" aws ecs list-tasks --cluster <cluster-name> --desired-status STOPPED --max-items 5 | jq -r '.taskArns[]' | while read task; do
    AWS_PAGER="" aws ecs describe-tasks --cluster <cluster-name> --tasks $task | jq -r '.tasks[0] | {stoppedReason, containers: [.containers[] | {name, exitCode, reason}]}'
done

# Get CloudWatch logs
AWS_PAGER="" aws logs tail /aws/ecs/<log-group> --follow --format short
```

## Success Criteria

**Deployment is successful when**:

1. ✅ CloudFormation stack reaches CREATE_COMPLETE
2. ✅ ECS service shows runningCount = desiredCount = 1
3. ✅ Tasks stay running for > 5 minutes without cycling
4. ✅ ALB health checks pass consistently
5. ✅ Load balancer DNS returns 200 OK from /health endpoint

## Next Steps

1. **Update minimal_app.py** with all recommended changes
2. **Add health endpoints** to backend/main.py
3. **Test locally** with Docker
4. **Synthesize CDK** and validate template
5. **Ask user permission** to deploy minimal stack
6. **Monitor actively** with all commands above
7. **Investigate logs immediately** if tasks cycle

## Key Learnings

- **Health check timing is critical** - 60 seconds is too short for DB-backed apps
- **Resource allocation matters** - 512MB may be insufficient
- **Separate health checks** - simple for container, comprehensive for ALB
- **Grace periods are essential** - give app time to start before health checks
- **Circuit breakers help** - automatic rollback on repeated failures
- **Monitor actively** - don't wait 90 minutes to check logs

## References

- [AWS re:Post: ECS service won't reach steady state](https://repost.aws/knowledge-center/ecs-service-not-steady-state)
- [AWS re:Post: Troubleshoot target deregistration](https://repost.aws/knowledge-center/ecs-troubleshoot-target-deregistration)
- [AWS Docs: Container restart policies](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/container-restart-policy.html)
- [AWS Docs: Task lifecycle](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-lifecycle-explanation.html)
- [AWS CDK Patterns: Fargate health checks](https://constructs.dev/packages/aws-cdk-lib)
