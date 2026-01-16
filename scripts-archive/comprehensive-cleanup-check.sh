#!/bin/bash
set -euo pipefail

echo "=== COMPREHENSIVE CLEANUP VERIFICATION ==="
echo "Checking deployment #85 cleanup status..."
echo ""

# 1. CloudFormation Stack
echo "1. CloudFormation Stack Status:"
if stack_info=$(AWS_PAGER="" aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --region us-east-1 2>&1); then
    status=$(echo "$stack_info" | jq -r '.Stacks[0].StackStatus')
    echo "   ❌ STACK EXISTS: $status"
    echo "   Stack must be deleted before deploying"
    exit 1
else
    echo "   ✅ No stack exists"
fi

# 2. GitHub Actions Workflows
echo ""
echo "2. GitHub Actions Workflows:"
workflows=$(gh run list --repo iseepatterns-jz/caseapp --limit 3 --json status,conclusion,databaseId,createdAt,workflowName)
running=$(echo "$workflows" | jq -r '.[] | select(.status == "in_progress" or .status == "queued") | .databaseId')

if [ -n "$running" ]; then
    echo "   ❌ WORKFLOWS RUNNING: $running"
    echo "   Wait for completion or cancel before deploying"
    exit 1
else
    echo "   ✅ No workflows running"
    echo "   Latest workflows:"
    echo "$workflows" | jq -r '.[] | "      - #\(.databaseId): \(.conclusion) (\(.workflowName))"'
fi

# 3. ECS Clusters
echo ""
echo "3. ECS Clusters:"
clusters=$(AWS_PAGER="" aws ecs list-clusters --region us-east-1 --query 'clusterArns[?contains(@, `CourtCase`)]' --output text)
if [ -n "$clusters" ]; then
    echo "   ❌ CLUSTERS EXIST: $clusters"
    exit 1
else
    echo "   ✅ No ECS clusters"
fi

# 4. RDS Instances
echo ""
echo "4. RDS Instances:"
rds=$(AWS_PAGER="" aws rds describe-db-instances --region us-east-1 --query 'DBInstances[?contains(DBInstanceIdentifier, `courtcase`)].{ID:DBInstanceIdentifier,Status:DBInstanceStatus}' --output json)
if [ "$rds" != "[]" ]; then
    echo "   ❌ RDS INSTANCES EXIST:"
    echo "$rds" | jq -r '.[] | "      - \(.ID): \(.Status)"'
    exit 1
else
    echo "   ✅ No RDS instances"
fi

# 5. Load Balancers
echo ""
echo "5. Application Load Balancers:"
albs=$(AWS_PAGER="" aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[?contains(LoadBalancerName, `Court`)].LoadBalancerName' --output text)
if [ -n "$albs" ]; then
    echo "   ❌ ALBs EXIST: $albs"
    exit 1
else
    echo "   ✅ No load balancers"
fi

# 6. VPCs
echo ""
echo "6. VPCs (CourtCase related):"
vpcs=$(AWS_PAGER="" aws ec2 describe-vpcs --region us-east-1 --filters "Name=tag:aws:cloudformation:stack-name,Values=CourtCaseManagementStack" --query 'Vpcs[].VpcId' --output text)
if [ -n "$vpcs" ]; then
    echo "   ❌ VPCs EXIST: $vpcs"
    exit 1
else
    echo "   ✅ No VPCs from our stack"
fi

# 7. Security Groups
echo ""
echo "7. Security Groups (CourtCase related):"
sgs=$(AWS_PAGER="" aws ec2 describe-security-groups --region us-east-1 --filters "Name=tag:aws:cloudformation:stack-name,Values=CourtCaseManagementStack" --query 'SecurityGroups[].GroupId' --output text)
if [ -n "$sgs" ]; then
    echo "   ❌ SECURITY GROUPS EXIST: $sgs"
    exit 1
else
    echo "   ✅ No security groups from our stack"
fi

# 8. S3 Buckets
echo ""
echo "8. S3 Buckets (CourtCase related):"
buckets=$(AWS_PAGER="" aws s3api list-buckets --query 'Buckets[?contains(Name, `courtcase`)].Name' --output text)
if [ -n "$buckets" ]; then
    echo "   ⚠️  BUCKETS EXIST: $buckets"
    echo "   (May be from previous deployments - will be reused or cleaned up)"
else
    echo "   ✅ No S3 buckets"
fi

# 9. Secrets Manager
echo ""
echo "9. Secrets Manager (deployment secrets):"
secrets=$(AWS_PAGER="" aws secretsmanager list-secrets --region us-east-1 --query 'SecretList[?contains(Name, `court-case`)].Name' --output text)
if [ -n "$secrets" ]; then
    echo "   ⚠️  SECRETS EXIST: $secrets"
    echo "   (May be from previous deployments - will be reused)"
else
    echo "   ✅ No deployment secrets"
fi

# Check for dockerhub-credentials (required)
if AWS_PAGER="" aws secretsmanager describe-secret --secret-id dockerhub-credentials --region us-east-1 >/dev/null 2>&1; then
    echo "   ✅ dockerhub-credentials exists (required)"
else
    echo "   ❌ dockerhub-credentials missing (required)"
    exit 1
fi

echo ""
echo "=== VERIFICATION COMPLETE ==="
echo "✅ Environment is CLEAN and READY for deployment #86"
echo ""
