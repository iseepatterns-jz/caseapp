# AWS Credentials Setup Guide

## Current Issue

The CI/CD pipeline is failing with "The security token included in the request is invalid" due to AWS IAM policy quota limits.

## Solution: Consolidated IAM Policy

### Step 1: Create Custom Inline Policy

Instead of using multiple managed policies (which hit the 10-policy limit), create a single custom inline policy:

1. **Go to AWS IAM Console** → Users → Select your deployment user
2. **Click "Add permissions"** → "Create inline policy"
3. **Switch to JSON tab** and paste the contents of `aws-iam-policy.json`
4. **Name the policy**: `CourtCaseManagementDeploymentPolicy`
5. **Click "Create policy"**

### Step 2: Remove Existing Managed Policies

Remove any existing managed policies to free up quota:

- Go to the user's "Permissions" tab
- Remove managed policies one by one
- Keep only the new inline policy

### Step 3: Generate New Access Keys

1. **Go to Security credentials tab** for your user
2. **Delete existing access keys** (if any)
3. **Create new access key** → Choose "Command Line Interface (CLI)"
4. **Download the credentials** or copy them securely

### Step 4: Update GitHub Secrets

1. **Go to your GitHub repository**: https://github.com/iseepatterns-jz/caseapp
2. **Settings** → **Secrets and variables** → **Actions**
3. **Update these secrets**:
   - `AWS_ACCESS_KEY_ID`: Your new access key ID
   - `AWS_SECRET_ACCESS_KEY`: Your new secret access key

### Step 5: Test the Deployment

1. **Go to Actions tab** in your GitHub repository
2. **Re-run the failed workflow** or push a new commit to trigger deployment
3. **Monitor the "deploy-production" job** to ensure it passes

## Alternative: Minimal Managed Policies Approach

If you prefer managed policies, use only these 2 (stays under 10-policy limit):

1. **PowerUserAccess** - Provides full access except IAM user/group/role/policy management
2. **IAMFullAccess** - Provides IAM permissions needed for CDK

This gives you comprehensive permissions while staying under the quota.

## Verification Commands

After updating credentials, verify they work:

```bash
# Test AWS credentials
aws sts get-caller-identity

# Test CDK permissions
aws cloudformation describe-stacks --region us-east-1

# Test S3 permissions
aws s3 ls
```

## Troubleshooting

### If deployment still fails:

1. **Check AWS region**: Ensure you're deploying to `us-east-1`
2. **Verify account limits**: Check if you have service limits that prevent resource creation
3. **Check CloudFormation events**: Look at the stack events in AWS Console for specific errors
4. **Enable CDK debug**: Add `--debug` flag to CDK commands for verbose output

### Common Issues:

- **VPC limits**: Default limit is 5 VPCs per region
- **Elastic IP limits**: Default limit is 5 per region
- **RDS subnet groups**: Check if you have existing subnet groups
- **Security group limits**: Default limit is 2500 per VPC

## Security Best Practices

1. **Use least privilege**: The provided policy gives necessary permissions but review for your specific needs
2. **Rotate access keys**: Set up regular rotation (every 90 days)
3. **Enable CloudTrail**: Monitor API calls for security
4. **Use IAM roles**: Consider using IAM roles for EC2/ECS instead of access keys where possible

## Next Steps After Successful Deployment

1. **Verify all services are running**:

   ```bash
   # Check ECS services
   aws ecs list-services --cluster CourtCaseCluster

   # Check RDS instance
   aws rds describe-db-instances

   # Check load balancer
   aws elbv2 describe-load-balancers
   ```

2. **Run database migrations**:

   ```bash
   # Connect to ECS and run migrations
   ./scripts/migrate-database.sh
   ```

3. **Test the application**:

   - Visit the load balancer URL
   - Check `/health` endpoint
   - Verify `/docs` API documentation

4. **Set up monitoring**:
   - CloudWatch dashboards
   - Application logs
   - Performance metrics

## Support

If you continue to have issues:

1. Check the GitHub Actions logs for specific error messages
2. Review AWS CloudFormation events in the console
3. Verify all prerequisites are met in the deployment checklist
