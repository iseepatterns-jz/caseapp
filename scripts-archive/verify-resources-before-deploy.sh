#!/bin/bash

# Verify AWS resources are in clean state before new deployment
# Checks CloudFormation, ECS, RDS, and other resources

set -euo pipefail

# Disable pagers
export AWS_PAGER=""
stty -ixon -ixoff 2>/dev/null || true

STACK_NAME="CourtCaseManagementStack"
REGION="us-east-1"

echo "=== Pre-Deployment Resource Verification ==="
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo "Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

ISSUES_FOUND=0

# 1. Check CloudFormation Stack
echo "1. Checking CloudFormation Stack..."
CFN_STATUS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" 2>/dev/null | jq -r '.Stacks[0].StackStatus' || echo "STACK_NOT_FOUND")

if [[ "$CFN_STATUS" == "STACK_NOT_FOUND" ]]; then
    echo "   ✅ No existing stack found - clean state"
elif [[ "$CFN_STATUS" =~ COMPLETE|FAILED ]]; then
    echo "   ⚠️  Stack exists with status: $CFN_STATUS"
    echo "   Stack should be deleted before new deployment"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
elif [[ "$CFN_STATUS" =~ IN_PROGRESS|PENDING ]]; then
    echo "   ❌ Stack operation in progress: $CFN_STATUS"
    echo "   CANNOT deploy - wait for operation to complete"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo "   ⚠️  Unexpected stack status: $CFN_STATUS"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi
echo ""

# 2. Check ECS Clusters
echo "2. Checking ECS Clusters..."
ECS_CLUSTERS=$(aws ecs list-clusters --region "$REGION" 2>/dev/null | \
    jq -r '.clusterArns[]' | grep -i court || echo "")

if [[ -z "$ECS_CLUSTERS" ]]; then
    echo "   ✅ No ECS clusters found - clean state"
else
    echo "   ⚠️  Found ECS cluster(s):"
    echo "$ECS_CLUSTERS" | while read -r cluster; do
        CLUSTER_NAME=$(basename "$cluster")
        echo "      - $CLUSTER_NAME"
        
        # Check for running services
        SERVICES=$(aws ecs list-services --cluster "$cluster" --region "$REGION" 2>/dev/null | \
            jq -r '.serviceArns[]' || echo "")
        
        if [[ -n "$SERVICES" ]]; then
            echo "        Services: $(echo "$SERVICES" | wc -l | tr -d ' ')"
        fi
    done
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi
echo ""

# 3. Check RDS Instances
echo "3. Checking RDS Instances..."
RDS_INSTANCES=$(aws rds describe-db-instances --region "$REGION" 2>/dev/null | \
    jq -r '.DBInstances[] | select(.DBInstanceIdentifier | contains("courtcase")) | .DBInstanceIdentifier' || echo "")

if [[ -z "$RDS_INSTANCES" ]]; then
    echo "   ✅ No RDS instances found - clean state"
else
    echo "   ⚠️  Found RDS instance(s):"
    echo "$RDS_INSTANCES" | while read -r instance; do
        STATUS=$(aws rds describe-db-instances \
            --db-instance-identifier "$instance" \
            --region "$REGION" 2>/dev/null | \
            jq -r '.DBInstances[0].DBInstanceStatus')
        echo "      - $instance: $STATUS"
    done
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi
echo ""

# 4. Check Load Balancers
echo "4. Checking Application Load Balancers..."
ALBS=$(aws elbv2 describe-load-balancers --region "$REGION" 2>/dev/null | \
    jq -r '.LoadBalancers[] | select(.LoadBalancerName | contains("Court")) | .LoadBalancerName' || echo "")

if [[ -z "$ALBS" ]]; then
    echo "   ✅ No load balancers found - clean state"
else
    echo "   ⚠️  Found load balancer(s):"
    echo "$ALBS" | while read -r alb; do
        echo "      - $alb"
    done
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi
echo ""

# 5. Check Security Groups
echo "5. Checking Security Groups..."
SGS=$(aws ec2 describe-security-groups --region "$REGION" 2>/dev/null | \
    jq -r '.SecurityGroups[] | select(.GroupName | contains("CourtCase")) | .GroupId' || echo "")

if [[ -z "$SGS" ]]; then
    echo "   ✅ No security groups found - clean state"
else
    echo "   ⚠️  Found security group(s):"
    echo "$SGS" | while read -r sg; do
        SG_NAME=$(aws ec2 describe-security-groups \
            --group-ids "$sg" \
            --region "$REGION" 2>/dev/null | \
            jq -r '.SecurityGroups[0].GroupName')
        echo "      - $sg ($SG_NAME)"
    done
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi
echo ""

# 6. Check Secrets Manager
echo "6. Checking Secrets Manager..."
SECRETS=$(aws secretsmanager list-secrets --region "$REGION" 2>/dev/null | \
    jq -r '.SecretList[] | select(.Name | contains("court-case")) | .Name' || echo "")

if [[ -z "$SECRETS" ]]; then
    echo "   ✅ No secrets found - clean state"
else
    echo "   ℹ️  Found secret(s) (may be retained):"
    echo "$SECRETS" | while read -r secret; do
        echo "      - $secret"
    done
    # Secrets are often retained, so don't count as issue
fi
echo ""

# Summary
echo "=== Verification Summary ==="
if [[ $ISSUES_FOUND -eq 0 ]]; then
    echo "✅ All checks passed - SAFE TO DEPLOY"
    echo ""
    echo "You can now deploy the fix:"
    echo "  git push origin main"
    exit 0
else
    echo "⚠️  Found $ISSUES_FOUND issue(s) - REVIEW BEFORE DEPLOYING"
    echo ""
    echo "Recommendations:"
    if [[ "$CFN_STATUS" =~ IN_PROGRESS|PENDING ]]; then
        echo "  1. Wait for CloudFormation operation to complete"
        echo "  2. Run this script again to verify"
    elif [[ "$CFN_STATUS" != "STACK_NOT_FOUND" ]]; then
        echo "  1. Delete CloudFormation stack:"
        echo "     aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION"
        echo "  2. Wait for deletion to complete (5-10 minutes)"
        echo "  3. Run this script again to verify"
    else
        echo "  1. Review resources listed above"
        echo "  2. Manually clean up if needed"
        echo "  3. Run this script again to verify"
    fi
    exit 1
fi
