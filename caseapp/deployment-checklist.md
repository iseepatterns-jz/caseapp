# AWS Deployment Checklist

## Pre-Deployment Requirements

### ✅ AWS Account Setup

- [x] AWS Account with appropriate permissions
- [x] AWS CLI configured with credentials
- [x] CDK CLI installed (`npm install -g aws-cdk`)
- [x] IAM policy quota resolved (see AWS-CREDENTIALS-SETUP.md)
- [x] Consolidated IAM policy created and applied
- [x] New AWS access keys generated
- [x] GitHub Secrets updated (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `DOCKER_USERNAME`, `DOCKER_PASSWORD`)
- [x] Docker Hub credentials secret requirement noted for AWS Secrets Manager
- [x] AWS setup validated (`./scripts/validate-aws-setup.sh`)
- [x] CDK bootstrapped (done automatically during deployment)
- [ ] Domain name registered (optional, for custom domain)
- [ ] SSL certificate requested in AWS Certificate Manager

### ✅ Code Preparation

- [x] All tests passing (`npm test` and `pytest`)
- [x] Docker images building successfully (linux/amd64 architecture verified)
- [x] Environment variables configured for production
- [x] Database migrations ready
- [x] Static assets optimized (production build synced to S3)

### ✅ Security Configuration

- [x] Secrets stored in AWS Secrets Manager
- [x] IAM roles and policies reviewed
- [x] Security groups configured properly
- [x] VPC and subnet configuration validated
- [x] Encryption enabled for all data stores

### ✅ Compliance Requirements

- [ ] HIPAA compliance settings enabled
- [ ] SOC 2 controls implemented
- [x] Audit logging configured
- [ ] Data retention policies set
- [x] Backup and disaster recovery plan (documented in Reliability Guide)

## Deployment Steps

### 1. Bootstrap CDK (First Time Only)

```bash
cd infrastructure
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

### 2. Deploy Infrastructure

```bash
# Deploy all stacks
cdk deploy --all

# Or deploy specific stack
cdk deploy CourtCaseManagementStack
```

### 3. Post-Deployment Configuration

- [x] Database schema migration (executed via one-off ECS task)
- [ ] Initial admin user creation
- [x] AI services testing
- [x] Load balancer health checks
- [ ] Domain name configuration
- [ ] SSL certificate attachment

### 4. Validation Tests

- [x] Health check endpoints responding
- [x] Database connectivity verified
- [x] S3 bucket access working
- [x] AI services functional
- [x] Authentication flow working
- [x] File upload/download working (Production CloudFront serving UI)
- [x] Media streaming functional

## Monitoring Setup

### ✅ CloudWatch Configuration

- [x] Application logs streaming to CloudWatch
- [x] Custom metrics configured
- [x] Alarms set for critical metrics
- [x] Dashboard created for monitoring ([Link](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=CourtCase-Deployment-Monitoring))

### ✅ Security Monitoring

- [ ] AWS GuardDuty enabled
- [ ] AWS Config rules configured
- [x] CloudTrail logging enabled
- [ ] Security Hub activated

## Cost Optimization

### ✅ Resource Optimization

- [x] Right-sized EC2/Fargate instances
- [x] S3 lifecycle policies configured
- [x] RDS instance class optimized
- [x] ElastiCache node type appropriate
- [ ] Auto-scaling policies configured

## Backup and Recovery

### ✅ Data Protection

- [x] RDS automated backups enabled
- [x] S3 versioning and cross-region replication
- [ ] Database point-in-time recovery tested
- [x] Disaster recovery plan documented
- [x] Recovery time objectives defined
