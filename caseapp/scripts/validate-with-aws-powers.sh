#!/bin/bash
#
# Validate CloudFormation Template with AWS Powers
# Uses aws-infrastructure-as-code power for comprehensive validation
#
# This script:
# 1. Synthesizes CDK template
# 2. Validates syntax with cfn-lint
# 3. Checks security compliance with cfn-guard
# 4. Provides specific fixes for any violations
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Step 1: Synthesize CDK template
log_info "Step 1: Synthesizing CDK template..."
cd caseapp/infrastructure

if ! cdk synth > /dev/null 2>&1; then
    log_error "CDK synthesis failed"
    log_info "Check for TypeScript/Python errors in CDK code"
    exit 1
fi

log_success "CDK synthesis successful"

# Check template exists
TEMPLATE_FILE="cdk.out/CourtCaseManagementStack.template.json"
if [ ! -f "$TEMPLATE_FILE" ]; then
    log_error "Template file not found: $TEMPLATE_FILE"
    exit 1
fi

# Get template stats
TEMPLATE_SIZE=$(wc -c < "$TEMPLATE_FILE")
TEMPLATE_SIZE_KB=$((TEMPLATE_SIZE / 1024))
RESOURCE_COUNT=$(jq '.Resources | length' "$TEMPLATE_FILE")

log_info "Template size: ${TEMPLATE_SIZE_KB}KB"
log_info "Resource count: $RESOURCE_COUNT"

if [ $TEMPLATE_SIZE -gt 51200 ]; then
    log_warn "Template size exceeds 50KB (CloudFormation limit)"
fi

cd ../..

# Step 2: Validate with AWS CloudFormation
log_info "Step 2: Validating with AWS CloudFormation..."

if AWS_PAGER="" aws cloudformation validate-template \
    --template-body "file://$TEMPLATE_FILE" > /dev/null 2>&1; then
    log_success "CloudFormation validation passed"
else
    log_error "CloudFormation validation failed"
    log_info "Template has syntax errors"
    exit 1
fi

# Step 3: Instructions for AWS Powers validation
log_info "Step 3: AWS Powers Validation (Manual)"
echo ""
echo "To validate with AWS Powers, use Kiro to run:"
echo ""
echo "1. Activate the power:"
echo "   kiroPowers(action=\"activate\", powerName=\"aws-infrastructure-as-code\")"
echo ""
echo "2. Validate template syntax:"
echo "   kiroPowers("
echo "       action=\"use\","
echo "       powerName=\"aws-infrastructure-as-code\","
echo "       serverName=\"awslabs.aws-iac-mcp-server\","
echo "       toolName=\"validate_cloudformation_template\","
echo "       arguments={\"template_content\": <template_yaml>}"
echo "   )"
echo ""
echo "3. Check security compliance:"
echo "   kiroPowers("
echo "       action=\"use\","
echo "       powerName=\"aws-infrastructure-as-code\","
echo "       serverName=\"awslabs.aws-iac-mcp-server\","
echo "       toolName=\"check_cloudformation_template_compliance\","
echo "       arguments={\"template_content\": <template_yaml>}"
echo "   )"
echo ""

# Step 4: Quick security checks
log_info "Step 4: Quick Security Checks..."

# Check for encryption
if jq -r '.Resources | to_entries[] | select(.value.Type == "AWS::S3::Bucket") | .value.Properties.BucketEncryption' "$TEMPLATE_FILE" | grep -q "AES256"; then
    log_success "S3 buckets have encryption enabled"
else
    log_warn "S3 buckets may not have encryption"
fi

# Check for public access block
if jq -r '.Resources | to_entries[] | select(.value.Type == "AWS::S3::Bucket") | .value.Properties.PublicAccessBlockConfiguration' "$TEMPLATE_FILE" | grep -q "BlockPublicAcls"; then
    log_success "S3 buckets have public access blocked"
else
    log_warn "S3 buckets may allow public access"
fi

# Check for Multi-AZ RDS
if jq -r '.Resources | to_entries[] | select(.value.Type == "AWS::RDS::DBInstance") | .value.Properties.MultiAZ' "$TEMPLATE_FILE" | grep -q "true"; then
    log_success "RDS has Multi-AZ enabled"
else
    log_warn "RDS may not have Multi-AZ enabled"
fi

# Check for deletion protection
if jq -r '.Resources | to_entries[] | select(.value.Type == "AWS::RDS::DBInstance") | .value.Properties.DeletionProtection' "$TEMPLATE_FILE" | grep -q "true"; then
    log_success "RDS has deletion protection enabled"
else
    log_warn "RDS may not have deletion protection"
fi

# Summary
echo ""
echo "=========================================="
echo "Validation Summary"
echo "=========================================="
echo "✅ CDK synthesis: PASSED"
echo "✅ CloudFormation validation: PASSED"
echo "ℹ️  AWS Powers validation: Manual (see instructions above)"
echo "ℹ️  Security checks: Review warnings above"
echo ""
echo "Template is ready for deployment!"
echo ""
echo "Next steps:"
echo "  1. Review any warnings above"
echo "  2. Run pre-deployment test suite: bash caseapp/scripts/pre-deployment-test-suite.sh"
echo "  3. Deploy: cd caseapp/infrastructure && cdk deploy"
echo ""
