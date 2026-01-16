# Scripts Archive

**Purpose**: Organized archive of deployment, monitoring, and utility shell scripts.

**Date Created**: January 16, 2026  
**Total Scripts**: 30 files

---

## 📂 Directory Organization

This directory contains all shell scripts that were previously in the root directory, organized by purpose.

---

## 📋 Script Categories

### 🚀 Deployment Scripts

**Deployment coordination and execution:**

- `deploy-aws.sh` - Main AWS deployment script (in caseapp/scripts/)
- `deployment_notifier.sh` - Deployment notifications
- `deployment-coordinator.sh` - Deployment coordination (in caseapp/scripts/)

### 📊 Monitoring Scripts

**Deployment and resource monitoring:**

- `monitor_deployment.sh` - General deployment monitoring
- `monitor-deployment-68.sh` - Deployment #68 monitoring
- `monitor-deployment-84.sh` - Deployment #84 monitoring
- `monitor-deployment-85.sh` - Deployment #85 monitoring
- `monitor-deployment-86.sh` - Deployment #86 monitoring
- `monitor-deployment-87.sh` - Deployment #87 monitoring
- `monitor-deployment-89.sh` - Deployment #89 monitoring
- `monitor-deployment-90.sh` - Deployment #90 monitoring
- `monitor-deployment-failure.sh` - Failure monitoring
- `monitor-deployment-status.sh` - Status monitoring
- `monitor-ecs-tasks-84.sh` - ECS task monitoring #84
- `monitor-ecs-tasks-85.sh` - ECS task monitoring #85
- `monitor-ecs-tasks-89.sh` - ECS task monitoring #89
- `monitor-ecs-tasks-90.sh` - ECS task monitoring #90
- `monitor-ecs-tasks-immediate.sh` - Immediate ECS monitoring
- `monitor-rds-deletion.sh` - RDS deletion monitoring
- `monitor-stack-deletion-84.sh` - Stack deletion #84
- `monitor-stack-deletion-89.sh` - Stack deletion #89
- `monitor-stack-deletion.sh` - General stack deletion

### 💬 Slack Integration Scripts

**Slack communication and notifications:**

- `ask-user-via-slack.sh` - Ask user questions via Slack
- `kiro-slack-question.sh` - Kiro Slack question handler
- `slack-question-poller.sh` - Poll for Slack responses
- `slack-bot-join-channels.sh` - Bot channel joining

### 🧹 Cleanup Scripts

**Resource cleanup and verification:**

- `comprehensive-cleanup-check.sh` - Comprehensive cleanup verification
- `wait-for-stack-deletion.sh` - Wait for stack deletion
- `wait-for-verification.sh` - Wait for verification

### ✅ Validation Scripts

**Pre-deployment validation:**

- `run_validation.sh` - Run validation checks
- `test-before-deploy.sh` - Pre-deployment testing
- `verify-resources-before-deploy.sh` - Resource verification (in root)

### 🔍 Verification Scripts

**Resource and deployment verification:**

- `verify-resources-before-deploy.sh` - Pre-deployment verification (in root)

---

## 🎯 Most Important Scripts

### For Deployment

1. **caseapp/scripts/deploy-aws.sh** - Main deployment script
2. **caseapp/scripts/deployment-coordinator.sh** - Deployment coordination
3. **verify-resources-before-deploy.sh** - Pre-deployment checks (in root)

### For Monitoring

1. **monitor_deployment.sh** - General deployment monitoring
2. **monitor-ecs-tasks-immediate.sh** - Immediate ECS monitoring
3. **monitor-deployment-status.sh** - Status monitoring

### For Slack

1. **ask-user-via-slack.sh** - Ask questions via Slack
2. **slack-question-poller.sh** - Poll for responses
3. **kiro-slack-question.sh** - Question handler

### For Cleanup

1. **comprehensive-cleanup-check.sh** - Cleanup verification
2. **wait-for-stack-deletion.sh** - Wait for deletion

---

## 📖 Script Usage

### Deployment Monitoring

```bash
# Monitor deployment in background
bash scripts-archive/monitor_deployment.sh &

# Monitor ECS tasks immediately
bash scripts-archive/monitor-ecs-tasks-immediate.sh

# Monitor deployment status
bash scripts-archive/monitor-deployment-status.sh
```

### Slack Communication

```bash
# Ask user via Slack
bash scripts-archive/ask-user-via-slack.sh "Question text"

# Poll for Slack response
bash scripts-archive/slack-question-poller.sh "#channel" "Question"

# Kiro Slack question handler
bash scripts-archive/kiro-slack-question.sh
```

### Cleanup and Verification

```bash
# Comprehensive cleanup check
bash scripts-archive/comprehensive-cleanup-check.sh

# Wait for stack deletion
bash scripts-archive/wait-for-stack-deletion.sh CourtCaseManagementStack

# Verify resources before deploy (in root)
bash verify-resources-before-deploy.sh
```

---

## 🔍 Finding Scripts

### By Purpose

```bash
# Deployment scripts
ls -1 scripts-archive/*deploy*.sh

# Monitoring scripts
ls -1 scripts-archive/monitor*.sh

# Slack scripts
ls -1 scripts-archive/*slack*.sh

# Cleanup scripts
ls -1 scripts-archive/*cleanup*.sh
ls -1 scripts-archive/*deletion*.sh
```

### By Deployment Number

```bash
# Deployment #84 scripts
ls -1 scripts-archive/*-84.sh

# Deployment #85 scripts
ls -1 scripts-archive/*-85.sh

# Deployment #89-90 scripts
ls -1 scripts-archive/*-89.sh
ls -1 scripts-archive/*-90.sh
```

---

## 📊 Statistics

- **Total Scripts**: 30 files
- **Monitoring Scripts**: 18 files
- **Slack Scripts**: 4 files
- **Cleanup Scripts**: 3 files
- **Validation Scripts**: 2 files
- **Deployment Scripts**: 3 files

---

## 🚀 Active Scripts

**These scripts are still actively used:**

- ✅ `verify-resources-before-deploy.sh` (in root) - Pre-deployment verification
- ✅ `caseapp/scripts/deploy-aws.sh` - Main deployment
- ✅ `caseapp/scripts/deployment-coordinator.sh` - Coordination
- ✅ `caseapp/scripts/deployment-monitor.sh` - Monitoring

**These scripts are archived (historical reference):**

- 📦 Deployment-specific monitoring scripts (68, 84-90)
- 📦 Historical cleanup scripts
- 📦 Old validation scripts

---

## 🔄 Maintenance

**When to add scripts here:**

- Deployment-specific monitoring scripts after deployment completes
- Cleanup scripts after successful cleanup
- Validation scripts that are no longer actively used
- Historical reference scripts

**When to keep scripts in root/caseapp/scripts:**

- Actively used deployment scripts
- Current monitoring scripts
- Pre-deployment verification scripts
- Scripts referenced in documentation

---

## 📝 Script Naming Convention

- `monitor-deployment-XX.sh` - Deployment-specific monitoring (XX = deployment number)
- `monitor-ecs-tasks-XX.sh` - ECS task monitoring (XX = deployment number)
- `monitor-stack-deletion-XX.sh` - Stack deletion monitoring (XX = deployment number)
- `*-slack*.sh` - Slack integration scripts
- `*cleanup*.sh` - Cleanup scripts
- `*validation*.sh` - Validation scripts

---

## 🔗 Related Directories

- **docs-archive/** - Deployment documentation
- **logs-archive/** - Deployment logs
- **caseapp/scripts/** - Active deployment scripts

---

## 📞 Support

**If you need to use a script:**

1. Check if it's still relevant (deployment-specific scripts are historical)
2. Review the script content before running
3. Update paths if needed (scripts may reference old locations)
4. Consider using active scripts in `caseapp/scripts/` instead

---

**Last Updated**: January 16, 2026  
**Status**: Archived and Organized  
**Purpose**: Historical reference and script organization
