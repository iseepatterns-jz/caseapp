# Deployment Troubleshooting Guide

## Recent Fixes Applied

### 1. PostgreSQL Version Issue ✅

**Problem**: CDK was using specific PostgreSQL version `VER_15_15` which may not be available in all regions.
**Fix**: Changed to `VER_15` to use the latest available 15.x version.

### 2. Docker Image Registry Mismatch ✅

**Problem**: CDK was hardcoded to use `iseepatterns/` Docker images, but CI/CD pushes to `${{ secrets.DOCKER_USERNAME }}/`.
**Fix**: Made Docker username configurable via CDK context parameter.

### 3. CDK Version Update ✅

**Problem**: Using older CDK version that may have compatibility issues.
**Fix**: Updated to CDK 2.160.0 and latest constructs version.

## Verification Steps

### 1. Check GitHub Secrets

Ensure these secrets are configured in your GitHub repository:

```bash
# Required secrets:
DOCKER_USERNAME=your_docker_hub_username
DOCKER_PASSWORD=your_docker_hub_password_or_token
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
```

### 2. Verify AWS Permissions

Your AWS credentials need these permissions:

- CloudFormation (full access)
- ECS (full access)
- RDS (full access)
- S3 (full access)
- IAM (create/manage roles)
- VPC (create/manage networking)
- ElastiCache (full access)
- OpenSearch (full access)
- Cognito (full access)

### 3. Test Local Deployment

```bash
cd caseapp
export DOCKER_USERNAME=your_docker_username
./scripts/deploy-aws.sh deploy
```

## Common Issues and Solutions

### Issue: "CDK Bootstrap Required"

**Solution**: The workflow now automatically bootstraps CDK if needed.

### Issue: "Docker Image Not Found"

**Solution**: Ensure Docker images are built and pushed before deployment. The workflow handles this automatically.

### Issue: "PostgreSQL Version Not Available"

**Solution**: Fixed by using flexible version specification.

### Issue: "Permission Denied"

**Solution**: Check AWS IAM permissions and GitHub secrets configuration.

## Monitoring Deployment

### GitHub Actions

1. Go to Actions tab in GitHub repository
2. Click on the latest workflow run
3. Check each job for detailed logs

### AWS CloudFormation

1. Open AWS Console → CloudFormation
2. Find "CourtCaseManagementStack"
3. Check Events tab for deployment progress

### Application Health

After successful deployment:

```bash
# Get ALB DNS from outputs
ALB_DNS=$(aws cloudformation describe-stacks \
  --stack-name CourtCaseManagementStack \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' \
  --output text)

# Test health endpoint
curl http://$ALB_DNS/health

# Test API docs
curl http://$ALB_DNS/docs
```

## Next Steps After Successful Deployment

1. **Database Migration**: Run initial database setup
2. **Admin User**: Create first administrative user
3. **Domain Setup**: Configure custom domain (optional)
4. **SSL Certificate**: Set up HTTPS (recommended)
5. **Monitoring**: Configure CloudWatch alarms
6. **Backup Verification**: Ensure backups are working

## Getting Help

If deployment still fails after these fixes:

1. **Check GitHub Actions logs** for specific error messages
2. **Check CloudFormation Events** in AWS Console
3. **Review CloudWatch logs** for application-specific issues
4. **Verify all prerequisites** are met (AWS CLI, CDK CLI, Docker)

## Rollback Procedure

If you need to rollback:

```bash
cd caseapp
./scripts/deploy-aws.sh destroy
```

**Warning**: This will destroy all infrastructure and data. Use with caution.
