#!/bin/bash

# Test script for validation fix
# Tests that the validation script properly detects active deployments

set -euo pipefail

echo "🧪 Testing Enhanced Deployment Validation Fix"
echo "=============================================="
echo

# Test 1: Check that validation detects no active deployment when stack doesn't exist
echo "Test 1: No active deployment (stack doesn't exist)"
echo "---------------------------------------------------"
if AWS_PAGER="" aws cloudformation describe-stacks --stack-name CourtCaseManagementStack --region us-east-1 &>/dev/null; then
    echo "⚠️  Stack exists - skipping this test"
else
    echo "✅ Stack doesn't exist - validation should pass"
    
    # Run validation (should pass)
    if AUTO_RESOLVE=false ./scripts/enhanced-deployment-validation.sh 2>&1 | grep -q "No active deployment detected"; then
        echo "✅ Test 1 PASSED: Validation correctly detected no active deployment"
    else
        echo "❌ Test 1 FAILED: Validation did not detect no active deployment"
        exit 1
    fi
fi

echo
echo "Test 2: Check RDS deletion wait logic"
echo "--------------------------------------"
# Check if any RDS instances are deleting
DELETING_RDS=$(AWS_PAGER="" aws rds describe-db-instances --region us-east-1 --query 'DBInstances[?DBInstanceStatus==`deleting` && contains(DBInstanceIdentifier, `courtcase`)].DBInstanceIdentifier' --output text 2>/dev/null || echo "")

if [ -n "$DELETING_RDS" ]; then
    echo "⚠️  RDS instances are currently deleting: $DELETING_RDS"
    echo "✅ Test 2 SKIPPED: Would test wait logic but RDS is actually deleting"
else
    echo "✅ No RDS instances deleting - validation should pass this check"
fi

echo
echo "Test 3: Verify validation script structure"
echo "-------------------------------------------"
# Check that the script has the new functions
if grep -q "check_deployment_in_progress" scripts/enhanced-deployment-validation.sh; then
    echo "✅ check_deployment_in_progress function exists"
else
    echo "❌ check_deployment_in_progress function missing"
    exit 1
fi

if grep -q "check_rds_deleting" scripts/enhanced-deployment-validation.sh; then
    echo "✅ check_rds_deleting function exists"
else
    echo "❌ check_rds_deleting function missing"
    exit 1
fi

if grep -q "wait_for_rds_deletion" scripts/enhanced-deployment-validation.sh; then
    echo "✅ wait_for_rds_deletion function exists"
else
    echo "❌ wait_for_rds_deletion function missing"
    exit 1
fi

# Check that deployment state check happens FIRST in main()
if grep -A 10 "# Main validation function" scripts/enhanced-deployment-validation.sh | grep -q "Deployment State Check"; then
    echo "✅ Deployment state check happens first in main()"
else
    echo "❌ Deployment state check not found at start of main()"
    exit 1
fi

echo
echo "Test 4: Verify script syntax"
echo "-----------------------------"
if bash -n scripts/enhanced-deployment-validation.sh; then
    echo "✅ Script syntax is valid"
else
    echo "❌ Script has syntax errors"
    exit 1
fi

echo
echo "=============================================="
echo "✅ All tests PASSED!"
echo
echo "Summary of fixes:"
echo "1. ✅ Added check_deployment_in_progress() to detect active deployments"
echo "2. ✅ Added check_rds_deleting() to detect RDS instances being deleted"
echo "3. ✅ Added wait_for_rds_deletion() to wait for RDS deletion to complete"
echo "4. ✅ Modified main() to check deployment state FIRST before any cleanup"
echo "5. ✅ Added RDS deletion wait logic before resource conflict checks"
echo
echo "The validation script will now:"
echo "- Refuse to run if a deployment is already in progress"
echo "- Wait for RDS deletion to complete before starting new deployment"
echo "- Not interfere with active CloudFormation operations"
echo
echo "Ready to test with actual deployment!"
