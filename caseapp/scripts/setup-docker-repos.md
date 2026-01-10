# Docker Repository Setup Guide

## Required Docker Hub Repositories

The CI/CD pipeline requires these Docker Hub repositories to be created:

1. `{DOCKER_USERNAME}/court-case-backend`
2. `{DOCKER_USERNAME}/court-case-frontend`
3. `{DOCKER_USERNAME}/court-case-media`

## Steps to Create Repositories

### Option 1: Via Docker Hub Web Interface

1. Go to https://hub.docker.com
2. Sign in with your Docker Hub account
3. Click "Create Repository"
4. Create each repository with these names:
   - `court-case-backend`
   - `court-case-frontend`
   - `court-case-media`
5. Set visibility to "Public" (or "Private" if you have a paid plan)

### Option 2: Via Docker CLI (if repositories don't exist, they'll be created on first push)

The repositories will be automatically created when the CI/CD pipeline pushes to them for the first time, provided your Docker Hub credentials are correct.

## Verify GitHub Secrets

Make sure these secrets are set in your GitHub repository:

1. Go to your GitHub repository
2. Click Settings → Secrets and variables → Actions
3. Verify these secrets exist:
   - `DOCKER_USERNAME`: Your Docker Hub username
   - `DOCKER_PASSWORD`: Your Docker Hub password or access token

## Test Docker Login Locally

```bash
# Test if your credentials work
echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

# If successful, you should see "Login Succeeded"
```

## Common Issues

1. **Repository doesn't exist**: Create repositories manually via Docker Hub web interface
2. **Authentication failed**: Check DOCKER_USERNAME and DOCKER_PASSWORD secrets
3. **Permission denied**: Ensure your Docker Hub account has permission to create repositories
4. **Rate limiting**: Docker Hub has pull/push rate limits for free accounts

## Next Steps

After creating the repositories:

1. Push a new commit to trigger the CI/CD pipeline
2. Monitor the GitHub Actions logs
3. Check that images are successfully pushed to Docker Hub
