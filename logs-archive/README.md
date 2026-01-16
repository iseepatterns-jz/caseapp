# Logs Archive

**Purpose**: Organized archive of deployment monitoring logs and execution records.

**Date Created**: January 16, 2026  
**Total Logs**: 24 files

---

## 📂 Directory Organization

This directory contains all log files from deployment monitoring, ECS task monitoring, and stack deletion operations.

---

## 📋 Log Categories

### 🚀 Deployment Monitoring Logs

**Deployment execution and monitoring:**

- `deployment-monitor.log` - General deployment monitoring
- `deployment-monitor-68.log` - Deployment #68 monitoring
- `deployment-82-monitor.log` - Deployment #82 monitoring
- `deployment-83-monitor.log` - Deployment #83 monitoring
- `deployment-84-monitor.log` - Deployment #84 monitoring
- `deployment-85-monitor.log` - Deployment #85 monitoring
- `deployment-86-monitor.log` - Deployment #86 monitoring
- `deployment-87-monitor.log` - Deployment #87 monitoring
- `deployment-88-monitor.log` - Deployment #88 monitoring
- `deployment-89-monitor.log` - Deployment #89 monitoring
- `deployment-90-monitor.log` - Deployment #90 monitoring
- `deployment-91-monitor.log` - Deployment #91 monitoring
- `deployment-94-monitor.log` - Deployment #94 monitoring ✅ SUCCESS

### 🐳 ECS Task Monitoring Logs

**ECS task startup and health monitoring:**

- `ecs-monitor.log` - General ECS monitoring
- `ecs-tasks-82-monitor.log` - ECS tasks #82
- `ecs-tasks-83-monitor.log` - ECS tasks #83
- `ecs-tasks-84-monitor.log` - ECS tasks #84
- `ecs-tasks-85-monitor.log` - ECS tasks #85
- `ecs-tasks-89-monitor.log` - ECS tasks #89
- `ecs-tasks-90-monitor.log` - ECS tasks #90
- `ecs-tasks-91-monitor.log` - ECS tasks #91

### 🗑️ Stack Deletion Logs

**CloudFormation stack deletion monitoring:**

- `stack-deletion.log` - General stack deletion
- `stack-deletion-monitor.log` - Stack deletion monitoring
- `stack-deletion-89.log` - Stack deletion #89

### 📝 Other Logs

**Miscellaneous logs:**

- `nohup.out` - Background process output

---

## 🎯 Most Important Logs

### Success Story

**Deployment #94** - The successful deployment:

- `deployment-94-monitor.log` - Monitoring log for successful deployment
- See also: `docs-archive/DEPLOYMENT-94-SUCCESS.md` for analysis

### Recent Deployments

**Deployments #82-91** - Recent attempts before success:

- `deployment-82-monitor.log` through `deployment-91-monitor.log`
- `ecs-tasks-82-monitor.log` through `ecs-tasks-91-monitor.log`

### Historical Reference

**Deployment #68** - Early deployment attempt:

- `deployment-monitor-68.log` - Historical reference

---

## 📊 Log Analysis

### Deployment Timeline

| Deployment | Status  | Logs Available                                  |
| ---------- | ------- | ----------------------------------------------- |
| #68        | Failed  | deployment-monitor-68.log                       |
| #82        | Failed  | deployment-82-monitor.log, ecs-tasks-82-monitor |
| #83        | Failed  | deployment-83-monitor.log, ecs-tasks-83-monitor |
| #84        | Failed  | deployment-84-monitor.log, ecs-tasks-84-monitor |
| #85        | Failed  | deployment-85-monitor.log, ecs-tasks-85-monitor |
| #86        | Failed  | deployment-86-monitor.log                       |
| #87        | Failed  | deployment-87-monitor.log                       |
| #88        | Failed  | deployment-88-monitor.log                       |
| #89        | Failed  | deployment-89-monitor.log, ecs-tasks-89-monitor |
| #90        | Failed  | deployment-90-monitor.log, ecs-tasks-90-monitor |
| #91        | Failed  | deployment-91-monitor.log, ecs-tasks-91-monitor |
| #94        | SUCCESS | deployment-94-monitor.log ✅                    |

---

## 🔍 Searching Logs

### Find Specific Errors

```bash
# Search for errors across all logs
grep -r "ERROR" logs-archive/

# Search for specific error patterns
grep -r "PostgreSQL" logs-archive/
grep -r "health check" logs-archive/
grep -r "task stopped" logs-archive/

# Search in specific deployment
grep "ERROR" logs-archive/deployment-94-monitor.log
```

### Find Deployment Patterns

```bash
# Find all deployment monitoring logs
ls -1 logs-archive/deployment-*-monitor.log

# Find all ECS task logs
ls -1 logs-archive/ecs-tasks-*-monitor.log

# Find stack deletion logs
ls -1 logs-archive/stack-deletion*.log
```

### Compare Deployments

```bash
# Compare failed vs successful deployment
diff logs-archive/deployment-90-monitor.log logs-archive/deployment-94-monitor.log

# Compare ECS task behavior
diff logs-archive/ecs-tasks-90-monitor.log logs-archive/ecs-tasks-91-monitor.log
```

---

## 📈 Common Log Patterns

### Successful Deployment (#94)

**Expected patterns in deployment-94-monitor.log:**

- Stack status: CREATE_COMPLETE
- ECS service: runningCount = desiredCount
- Tasks: Running without cycling
- Health checks: Passing

### Failed Deployments (#82-91)

**Common failure patterns:**

- Stack status: CREATE_FAILED or ROLLBACK_COMPLETE
- ECS tasks: Stopped with errors
- Health checks: Failing
- PostgreSQL version errors (before fix)

### ECS Task Issues

**Common patterns in ecs-tasks-\*-monitor.log:**

- Task cycling (starting and stopping repeatedly)
- Health check failures
- Database connection errors
- Resource exhaustion

---

## 🔗 Related Documentation

**For each deployment, see corresponding documentation:**

- **Deployment #68**: `docs-archive/DEPLOYMENT-67-FAILURE-ANALYSIS.md`
- **Deployment #82-91**: Various failure analysis docs in `docs-archive/`
- **Deployment #94**: `docs-archive/DEPLOYMENT-94-SUCCESS.md` ✅

---

## 📊 Statistics

- **Total Logs**: 24 files
- **Deployment Logs**: 13 files
- **ECS Task Logs**: 8 files
- **Stack Deletion Logs**: 3 files
- **Deployments Tracked**: 12 deployments (#68, #82-91, #94)
- **Success Rate**: 1/12 (8.3%)

---

## 🎯 Key Learnings from Logs

### What Logs Revealed

1. **PostgreSQL Version Issues** - Repeated errors about invalid version
2. **Task Cycling** - Tasks starting and stopping due to health check failures
3. **Resource Constraints** - Memory and CPU issues in early deployments
4. **Health Check Timing** - Insufficient grace periods causing failures
5. **Database Dependencies** - Health checks requiring database caused cycling

### How Logs Helped

- Identified PostgreSQL version as critical blocker
- Showed task cycling patterns
- Revealed health check timing issues
- Demonstrated resource allocation problems
- Guided troubleshooting efforts

---

## 🔄 Maintenance

**When to add logs here:**

- After deployment completes (success or failure)
- After monitoring scripts finish
- When logs are no longer actively needed
- For historical reference

**When to clean up logs:**

- After successful deployment and verification
- When logs are very old (>30 days)
- When disk space is needed
- After extracting key learnings

---

## 📝 Log Naming Convention

- `deployment-XX-monitor.log` - Deployment monitoring (XX = deployment number)
- `ecs-tasks-XX-monitor.log` - ECS task monitoring (XX = deployment number)
- `stack-deletion-XX.log` - Stack deletion (XX = deployment number)
- `*-monitor.log` - General monitoring logs

---

## 🚀 Using Logs for Troubleshooting

### Step 1: Identify Deployment

```bash
# List all deployment logs
ls -1 logs-archive/deployment-*-monitor.log
```

### Step 2: Review Deployment Log

```bash
# View specific deployment
less logs-archive/deployment-94-monitor.log

# Search for errors
grep -i "error\|fail\|stop" logs-archive/deployment-94-monitor.log
```

### Step 3: Check ECS Task Logs

```bash
# View ECS task behavior
less logs-archive/ecs-tasks-94-monitor.log

# Look for task cycling
grep "STOPPED\|RUNNING" logs-archive/ecs-tasks-94-monitor.log
```

### Step 4: Compare with Documentation

```bash
# Cross-reference with documentation
cat docs-archive/DEPLOYMENT-94-SUCCESS.md
```

---

## 📞 Support

**If you need to analyze logs:**

1. Identify the deployment number
2. Review deployment monitoring log
3. Check ECS task logs if available
4. Cross-reference with documentation in `docs-archive/`
5. Search for error patterns
6. Compare with successful deployment (#94)

---

## 🎉 Success Story

**Deployment #94** - After 5+ days and 94 attempts:

- ✅ Stack: CREATE_COMPLETE
- ✅ ECS Tasks: Running without cycling
- ✅ Health Checks: Passing
- ✅ Database: Connected
- ✅ All Services: Healthy

**Key Fix**: PostgreSQL version changed from CDK constants to explicit version 15.15

See `logs-archive/deployment-94-monitor.log` for the successful deployment log.

---

**Last Updated**: January 16, 2026  
**Status**: Archived and Organized  
**Purpose**: Historical reference and troubleshooting resource
