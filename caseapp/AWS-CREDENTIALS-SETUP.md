# AWS Credentials Setup Guide

## Current Issue

The deployment is failing with "The security token included in the request is invalid" which indicates AWS credentials are not properly configured.

## Required GitHub Secrets

You need to add these secrets to your GitHub repository:

### 1. AWS_ACCESS_KEY_ID

- Your AWS access key ID
- Format: `AKIA...` (20 characters)

### 2. AWS_SECRET_ACCESS_KEY

- Your AWS secret access key
- Format: 40-character string

### 3. Optional: AWS_SESSION_TOKEN

- Only needed if using temporary credentials
- Not required for IAM user credentials

## How to Add GitHub Secrets

1. **Go to your GitHub repository**: https://github.com/iseepatterns-jz/caseapp
2. **Click Settings** (in the repository, not your profile)
3. **Click "Secrets and variables"** → **"Actions"**
4. **Click "New repository secret"**
5. **Add each secret**:
   - Name: `AWS_ACCESS_KEY_ID`
   - Value: Your AWS access key ID
   - Click "Add secret"
   - Repeat for `AWS_SECRET_ACCESS_KEY`

## How to Get AWS Credentials

### Option 1: Create IAM User (Recommended)

1. Go to AWS Console → IAM → Users
2. Click "Create user"
3. Username: `github-actions-caseapp`
4. Select "Programmatic access"
5. Attach policies:
   - `PowerUserAccess` (or create custom policy)
   - `IAMReadOnlyAccess`
6. Download the credentials CSV file
7. Use the Access Key ID and Secret Access Key

### Option 2: Use Existing IAM User

If you already have an IAM user:

1. Go to AWS Console → IAM → Users
2. Select your user
3. Go to "Security credentials" tab
4. Click "Create access key"
5. Choose "Command Line Interface (CLI)"
6. Download the credentials

## Required AWS Permissions

The IAM user needs these permissions for deployment:

- CloudFormation (full access)
- ECS (full access)
- VPC (full access)
- RDS (full access)
- ElastiCache (full access)
- S3 (full access)
- IAM (read access, create roles)
- EC2 (full access)
- Application Load Balancer (full access)

## Testing AWS Credentials

You can test your credentials locally:

```bash
# Configure AWS CLI
aws configure
# Enter your Access Key ID
# Enter your Secret Access Key
# Enter region: us-east-1
# Enter output format: json

# Test credentials
aws sts get-caller-identity
```

## Security Best Practices

1. **Use IAM User**: Don't use root account credentials
2. **Minimal Permissions**: Only grant necessary permissions
3. **Rotate Keys**: Regularly rotate access keys
4. **Monitor Usage**: Set up CloudTrail for API monitoring
5. **Use Temporary Credentials**: Consider AWS STS for temporary access

## Troubleshooting

### Error: "The security token included in the request is invalid"

- **Cause**: Invalid or missing AWS credentials
- **Solution**: Verify GitHub Secrets are correctly set

### Error: "Access Denied"

- **Cause**: Insufficient IAM permissions
- **Solution**: Add required permissions to IAM user

### Error: "Region not found"

- **Cause**: Invalid AWS region
- **Solution**: Ensure region is set to `us-east-1`

## Next Steps After Adding Credentials

1. Add the AWS credentials to GitHub Secrets
2. Re-run the failed GitHub Actions workflow
3. Monitor the deployment logs
4. Verify the infrastructure is created in AWS Console

## Alternative: AWS OIDC (Advanced)

For enhanced security, you can use OpenID Connect instead of long-lived credentials:

1. Create an OIDC identity provider in AWS
2. Create an IAM role that trusts GitHub Actions
3. Use `aws-actions/configure-aws-credentials@v4` with role assumption

This is more secure but requires additional setup.
