# Emergency Procedures Runbook

## Quick Reference

### Emergency Contacts

- **Operations Team**: ops-team@company.com | +1-555-OPS-TEAM | Slack: #ops-emergency
- **Engineering Team**: dev-team@company.com | +1-555-DEV-TEAM | Slack: #dev-emergency
- **Management**: management@company.com | +1-555-MGMT

### Critical Commands

**Immediate Health Check**:

```bash
curl -f https://<load-balancer-dns>/health || echo "SERVICE DOWN"
```

**Emergency Rollback**:

```bash
curl -X POST https://<load-balancer-dns>/api/v1/disaster-recovery/rollback/<cluster>/<service> \
  -H "Content-Type: application/json" \
  -d '{"snapshot_id": "latest", "dry_run": false}'
```

**Emergency Scaling**:

```bash
curl -X POST https://<load-balancer-dns>/api/v1/disaster-recovery/emergency-scale/<cluster>/<service> \
  -H "Content-Type: application/json" \
  -d '{"target_count": 10, "reason": "Emergency response"}'
```

## Incident Response Procedures

### Severity Levels

**P0 - Critical (Service Down)**

- Complete service unavailability
- Data loss or corruption
- Security breach
- Response Time: Immediate (0-15 minutes)

**P1 - High (Major Impact)**

- Significant performance degradation
- High error rates (>10%)
- Partial service unavailability
- Response Time: 15-60 minutes

**P2 - Medium (Minor Impact)**

- Minor performance issues
- Low error rates (5-10%)
- Non-critical feature unavailable
- Response Time: 1-4 hours

**P3 - Low (Minimal Impact)**

- Cosmetic issues
- Documentation problems
- Enhancement requests
- Response Time: Next business day

### P0 - Critical Incident Response

#### Immediate Actions (0-5 minutes)

1. **Assess Situation**

   ```bash
   # Check service health
   curl -f https://<load-balancer-dns>/health

   # Check comprehensive health
   curl https://<load-balancer-dns>/api/v1/health/comprehensive
   ```

2. **Notify Stakeholders**

   - Post in #ops-emergency Slack channel
   - Send email to ops-team@company.com
   - Call primary on-call engineer

3. **Check Automated Recovery**

   ```bash
   # Check if orchestration is handling the issue
   curl https://<load-balancer-dns>/api/v1/deployment-orchestration/status/<cluster>/<service>
   ```

4. **Activate Incident Commander**
   - Designate incident commander
   - Start incident bridge/call
   - Begin incident log

#### Short-term Response (5-30 minutes)

1. **Execute Emergency Rollback** (if deployment-related)

   ```bash
   # List available snapshots
   curl https://<load-balancer-dns>/api/v1/disaster-recovery/snapshots/<cluster>/<service>

   # Execute rollback to latest stable
   curl -X POST https://<load-balancer-dns>/api/v1/disaster-recovery/rollback/<cluster>/<service> \
     -H "Content-Type: application/json" \
     -d '{"snapshot_id": "latest", "dry_run": false}'
   ```

2. **Emergency Scaling** (if resource-related)

   ```bash
   # Scale up immediately
   curl -X POST https://<load-balancer-dns>/api/v1/disaster-recovery/emergency-scale/<cluster>/<service> \
     -H "Content-Type: application/json" \
     -d '{"target_count": 10, "reason": "P0 incident response"}'
   ```

3. **Run Comprehensive Diagnostics**

   ```bash
   # Get diagnostic report
   curl https://<load-balancer-dns>/api/v1/diagnostics/run-diagnostics

   # Check for critical issues
   curl https://<load-balancer-dns>/api/v1/diagnostics/issues?severity=critical
   ```

4. **Monitor Recovery Progress**

   ```bash
   # Monitor health score
   watch -n 30 'curl -s https://<load-balancer-dns>/api/v1/health/score'

   # Monitor error rates
   curl https://<load-balancer-dns>/api/v1/monitoring/metrics/<cluster>/<service>
   ```

#### Long-term Response (30+ minutes)

1. **Root Cause Analysis**

   - Review logs and metrics
   - Identify failure point
   - Document timeline

2. **Implement Permanent Fix**

   - Deploy code fixes if needed
   - Update configuration
   - Test thoroughly

3. **Post-Incident Activities**
   - Conduct post-mortem
   - Update runbooks
   - Implement preventive measures

### P1 - High Impact Response

#### Assessment (0-15 minutes)

1. **Identify Impact Scope**

   ```bash
   # Check error rates
   curl https://<load-balancer-dns>/api/v1/monitoring/metrics/<cluster>/<service>

   # Check affected endpoints
   curl -X POST https://<load-balancer-dns>/api/v1/deployment-validation/validate/<cluster>/<service>
   ```

2. **Determine Root Cause**

   ```bash
   # Run diagnostics
   curl https://<load-balancer-dns>/api/v1/diagnostics/run-diagnostics

   # Check resource utilization
   curl https://<load-balancer-dns>/api/v1/resource-optimization/analyze/<cluster>/<service>
   ```

#### Mitigation (15-60 minutes)

1. **Apply Quick Fixes**

   - Restart unhealthy tasks
   - Adjust resource allocation
   - Update configuration

2. **Monitor Improvement**

   ```bash
   # Track health score improvement
   curl https://<load-balancer-dns>/api/v1/health/score

   # Monitor performance metrics
   curl https://<load-balancer-dns>/api/v1/monitoring/metrics/<cluster>/<service>
   ```

## Common Emergency Scenarios

### Scenario 1: Complete Service Outage

**Symptoms**:

- Health check returns 503/504
- No healthy ECS tasks
- Load balancer shows no targets

**Response**:

```bash
# 1. Check ECS service status
aws ecs describe-services --cluster <cluster> --services <service>

# 2. Check task failures
aws ecs list-tasks --cluster <cluster> --service-name <service>

# 3. Emergency rollback
curl -X POST https://<load-balancer-dns>/api/v1/disaster-recovery/rollback/<cluster>/<service> \
  -d '{"snapshot_id": "latest", "dry_run": false}'

# 4. If rollback fails, execute recovery plan
curl -X POST https://<load-balancer-dns>/api/v1/disaster-recovery/execute-plan/service_rollback \
  -d '{"cluster_name": "<cluster>", "service_name": "<service>"}'
```

### Scenario 2: High Error Rate

**Symptoms**:

- Error rate > 10%
- 5xx responses increasing
- Application exceptions in logs

**Response**:

```bash
# 1. Check application logs
aws logs filter-log-events --log-group-name /ecs/<service> --filter-pattern "ERROR"

# 2. Run diagnostics
curl https://<load-balancer-dns>/api/v1/diagnostics/run-diagnostics

# 3. Check database connectivity
curl https://<load-balancer-dns>/api/v1/health/database

# 4. If database issues, check RDS status
aws rds describe-db-instances --db-instance-identifier <db-instance>

# 5. Consider rollback if recent deployment
curl -X POST https://<load-balancer-dns>/api/v1/disaster-recovery/rollback/<cluster>/<service>
```

### Scenario 3: Performance Degradation

**Symptoms**:

- Response times > 5 seconds
- High CPU/memory utilization
- Timeouts increasing

**Response**:

```bash
# 1. Check resource utilization
curl https://<load-balancer-dns>/api/v1/resource-optimization/analyze/<cluster>/<service>

# 2. Emergency scaling
curl -X POST https://<load-balancer-dns>/api/v1/disaster-recovery/emergency-scale/<cluster>/<service> \
  -d '{"target_count": 8, "reason": "Performance degradation"}'

# 3. Check for resource bottlenecks
curl https://<load-balancer-dns>/api/v1/diagnostics/run-diagnostics

# 4. Monitor improvement
watch -n 30 'curl -s https://<load-balancer-dns>/api/v1/health/score'
```

### Scenario 4: Database Connection Issues

**Symptoms**:

- Database connection errors
- Timeouts on database queries
- Health check failures

**Response**:

```bash
# 1. Check database health
curl https://<load-balancer-dns>/api/v1/health/database

# 2. Check RDS instance status
aws rds describe-db-instances --db-instance-identifier <db-instance>

# 3. Check security groups
aws ec2 describe-security-groups --group-ids <db-security-group>

# 4. Check connection pool
curl https://<load-balancer-dns>/api/v1/diagnostics/database-connections

# 5. Restart application if needed
aws ecs update-service --cluster <cluster> --service <service> --force-new-deployment
```

### Scenario 6: Database Schema Out of Sync

**Symptoms**:
- API returns `400 Bad Request` on specific endpoints (e.g., `/api/v1/audit/search`)
- Backend logs show `ProgrammingError: column ... does not exist`
- Alembic migrations fail or are stuck

**Response**:

1. **Verify Backend Connection Details**:
   Check ECS task environment variables for `DB_HOST`, `DB_USER`, etc.

2. **Execute Manual Schema Fix (via ECS Task)**:
   If standard migrations fail, execute a direct SQL fix using a one-off ECS Fargate task.

   > [!IMPORTANT]
   > The production RDS instance **requires SSL**. When executing manual Python scripts or SQL commands, ensure the connection string includes `ssl=require`.

   **Example Python Force Fix Script**:
   ```python
   # url = f'postgresql+asyncpg://{user}:{pass}@{host}:5432/{db}?ssl=require'
   # await conn.execute(text('ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...;'))
   # await conn.execute(text('DELETE FROM alembic_version; INSERT INTO alembic_version (version_num) VALUES (...);'))
   ```

3. **Synchronize Alembic**:
   Ensure `alembic_version` matches the latest migration ID to prevent future conflicts.

### Scenario 5: AWS Service Outage

**Symptoms**:

- AWS API errors
- Service unavailable in specific AZ
- Regional service disruption

**Response**:

```bash
# 1. Check AWS service health
curl https://status.aws.amazon.com/

# 2. Check service distribution across AZs
aws ecs describe-services --cluster <cluster> --services <service>

# 3. If single AZ affected, force redistribution
aws ecs update-service --cluster <cluster> --service <service> --force-new-deployment

# 4. Consider cross-region failover if available
# (This would require pre-configured cross-region setup)

# 5. Monitor AWS status updates
# Subscribe to AWS Health Dashboard notifications
```

## Monitoring and Alerting

### Critical Alerts

**Service Down Alert**:

```bash
# Immediate check
curl -f https://<load-balancer-dns>/health

# If down, check ECS service
aws ecs describe-services --cluster <cluster> --services <service>

# Check recent deployments
aws ecs list-tasks --cluster <cluster> --service-name <service>
```

**High Error Rate Alert**:

```bash
# Check current error rate
curl https://<load-balancer-dns>/api/v1/monitoring/metrics/<cluster>/<service>

# Check application logs
aws logs filter-log-events --log-group-name /ecs/<service> --filter-pattern "ERROR" --start-time $(date -d '5 minutes ago' +%s)000
```

**Performance Alert**:

```bash
# Check response times
curl https://<load-balancer-dns>/api/v1/monitoring/metrics/<cluster>/<service>

# Check resource utilization
curl https://<load-balancer-dns>/api/v1/resource-optimization/analyze/<cluster>/<service>
```

### Alert Response Matrix

| Alert Type              | Severity | Response Time | Actions                         |
| ----------------------- | -------- | ------------- | ------------------------------- |
| Service Down            | P0       | Immediate     | Emergency rollback, scaling     |
| High Error Rate         | P1       | 15 minutes    | Diagnostics, potential rollback |
| Performance Degradation | P1       | 15 minutes    | Resource analysis, scaling      |
| Database Issues         | P1       | 15 minutes    | Connection check, restart       |
| Security Issues         | P0       | Immediate     | Isolate, investigate, patch     |

## Recovery Validation

### Post-Recovery Checklist

After any emergency response, validate recovery:

1. **Health Checks**:

   ```bash
   # Basic health
   curl https://<load-balancer-dns>/health

   # Comprehensive health
   curl https://<load-balancer-dns>/api/v1/health/comprehensive

   # Health score should be > 80
   curl https://<load-balancer-dns>/api/v1/health/score
   ```

2. **Functional Testing**:

   ```bash
   # Run smoke tests
   curl -X POST https://<load-balancer-dns>/api/v1/deployment-validation/smoke-test/<cluster>/<service>

   # API validation
   curl -X POST https://<load-balancer-dns>/api/v1/deployment-validation/api-validation/<cluster>/<service>
   ```

3. **Performance Validation**:

   ```bash
   # Check response times
   curl https://<load-balancer-dns>/api/v1/monitoring/metrics/<cluster>/<service>

   # Run performance test
   curl -X POST https://<load-balancer-dns>/api/v1/deployment-validation/performance-test \
     -d '{"base_url": "https://<load-balancer-dns>", "concurrent_requests": 5, "duration_seconds": 30}'
   ```

4. **Monitoring Setup**:

   ```bash
   # Ensure monitoring is active
   curl https://<load-balancer-dns>/api/v1/monitoring/dashboard/<cluster>/<service>

   # Check alert configuration
   curl https://<load-balancer-dns>/api/v1/monitoring/alerts/status
   ```

## Communication Templates

### Initial Incident Notification

**Subject**: [P0/P1] Service Incident - <Service Name>

**Body**:

```
INCIDENT ALERT

Severity: P0/P1
Service: <Service Name>
Start Time: <Timestamp>
Impact: <Description of impact>
Status: Investigating

Initial Assessment:
- <Brief description of issue>
- <Affected components>
- <Current actions being taken>

Incident Commander: <Name>
Next Update: <Time>

Updates will be posted in #ops-emergency
```

### Resolution Notification

**Subject**: [RESOLVED] Service Incident - <Service Name>

**Body**:

```
INCIDENT RESOLVED

Severity: P0/P1
Service: <Service Name>
Start Time: <Timestamp>
Resolution Time: <Timestamp>
Duration: <Duration>

Root Cause:
<Brief description of root cause>

Resolution:
<Description of resolution steps>

Next Steps:
- Post-mortem scheduled for <Date/Time>
- Preventive measures to be implemented
- Monitoring enhanced

Incident Commander: <Name>
```

## Tools and Resources

### Essential Tools

1. **AWS CLI**: For direct AWS service management
2. **curl/httpie**: For API testing and health checks
3. **jq**: For JSON parsing and filtering
4. **watch**: For continuous monitoring
5. **Slack**: For team communication
6. **CloudWatch**: For metrics and logs

### Useful Commands

**Monitor Service Health**:

```bash
# Continuous health monitoring
watch -n 30 'curl -s https://<load-balancer-dns>/api/v1/health/score | jq .score'

# Monitor error rates
watch -n 60 'curl -s https://<load-balancer-dns>/api/v1/monitoring/metrics/<cluster>/<service> | jq .error_rate'
```

**Log Analysis**:

```bash
# Recent errors
aws logs filter-log-events --log-group-name /ecs/<service> --filter-pattern "ERROR" --start-time $(date -d '10 minutes ago' +%s)000

# Performance issues
aws logs filter-log-events --log-group-name /ecs/<service> --filter-pattern "slow" --start-time $(date -d '10 minutes ago' +%s)000
```

**Resource Monitoring**:

```bash
# ECS service status
aws ecs describe-services --cluster <cluster> --services <service> --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'

# Task health
aws ecs list-tasks --cluster <cluster> --service-name <service> --desired-status RUNNING
```

## Training and Preparedness

### Regular Drills

Conduct monthly emergency drills:

1. **Simulated Outage**: Practice complete service recovery
2. **Performance Issues**: Practice scaling and optimization
3. **Database Failures**: Practice database recovery procedures
4. **Security Incidents**: Practice security response procedures

### Knowledge Requirements

All on-call engineers should know:

1. **Service Architecture**: Understanding of system components
2. **Emergency Procedures**: This runbook and all procedures
3. **AWS Services**: ECS, RDS, CloudWatch, ALB configuration
4. **Monitoring Tools**: How to read dashboards and alerts
5. **Communication**: Incident communication procedures

### Documentation Updates

This runbook should be updated:

1. **After each incident**: Incorporate lessons learned
2. **Quarterly reviews**: Ensure accuracy and completeness
3. **Architecture changes**: Update procedures for new components
4. **Tool changes**: Update commands and procedures

## Appendix

### Service Configuration

**Cluster Name**: CourtCaseCluster
**Service Name**: BackendService
**Load Balancer DNS**: <load-balancer-dns>
**Region**: us-west-2

### API Endpoints Quick Reference

```
Health: GET /health
Comprehensive Health: GET /api/v1/health/comprehensive
Diagnostics: GET /api/v1/diagnostics/run-diagnostics
Metrics: GET /api/v1/monitoring/metrics/<cluster>/<service>
Rollback: POST /api/v1/disaster-recovery/rollback/<cluster>/<service>
Emergency Scale: POST /api/v1/disaster-recovery/emergency-scale/<cluster>/<service>
```

### AWS Resource ARNs

```
ECS Cluster: arn:aws:ecs:us-west-2:123456789012:cluster/CourtCaseCluster
ECS Service: arn:aws:ecs:us-west-2:123456789012:service/CourtCaseCluster/BackendService
Load Balancer: arn:aws:elasticloadbalancing:us-west-2:123456789012:loadbalancer/app/...
RDS Instance: arn:aws:rds:us-west-2:123456789012:db:court-case-db
```

Remember: When in doubt, escalate quickly. It's better to involve more people than needed than to let an incident escalate.
