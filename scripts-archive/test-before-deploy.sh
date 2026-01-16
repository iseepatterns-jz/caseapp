#!/bin/bash
#
# Quick Pre-Deployment Test Script
# Tests CDK synthesis and Docker build locally before pushing
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "Pre-Deployment Local Tests"
echo "=========================================="
echo ""

# Test 1: CDK Synthesis
echo -e "${BLUE}[TEST 1]${NC} CDK Template Synthesis"
cd caseapp/infrastructure

if cdk synth > /dev/null 2>&1; then
    echo -e "${GREEN}  ✅ PASS${NC} CDK synthesis successful"
    
    # Check template exists
    if [ -f "cdk.out/CourtCaseManagementStack.template.json" ]; then
        size=$(wc -c < "cdk.out/CourtCaseManagementStack.template.json")
        size_kb=$((size / 1024))
        echo -e "${BLUE}  ℹ️  INFO${NC} Template size: ${size_kb}KB"
    fi
else
    echo -e "${RED}  ❌ FAIL${NC} CDK synthesis failed"
    cd ../..
    exit 1
fi

cd ../..

# Test 2: Python Syntax Check
echo ""
echo -e "${BLUE}[TEST 2]${NC} Python Syntax Check"

if python3 -m py_compile caseapp/backend/core/service_manager.py 2>/dev/null; then
    echo -e "${GREEN}  ✅ PASS${NC} service_manager.py syntax OK"
else
    echo -e "${RED}  ❌ FAIL${NC} service_manager.py has syntax errors"
    exit 1
fi

if python3 -m py_compile caseapp/backend/main.py 2>/dev/null; then
    echo -e "${GREEN}  ✅ PASS${NC} main.py syntax OK"
else
    echo -e "${RED}  ❌ FAIL${NC} main.py has syntax errors"
    exit 1
fi

if python3 -m py_compile caseapp/backend/core/aws_service.py 2>/dev/null; then
    echo -e "${GREEN}  ✅ PASS${NC} aws_service.py syntax OK"
else
    echo -e "${RED}  ❌ FAIL${NC} aws_service.py has syntax errors"
    exit 1
fi

# Test 3: Import Path Validation
echo ""
echo -e "${BLUE}[TEST 3]${NC} Import Path Validation"

# Check that aws_service.py is in core/ directory
if [ -f "caseapp/backend/core/aws_service.py" ]; then
    echo -e "${GREEN}  ✅ PASS${NC} aws_service.py exists in core/ directory"
else
    echo -e "${RED}  ❌ FAIL${NC} aws_service.py not found in core/ directory"
    exit 1
fi

# Check that service_manager imports from core.aws_service
if grep -q "from core.aws_service import aws_service" caseapp/backend/core/service_manager.py; then
    echo -e "${GREEN}  ✅ PASS${NC} service_manager.py imports from core.aws_service"
else
    echo -e "${RED}  ❌ FAIL${NC} service_manager.py has incorrect import"
    exit 1
fi

# Check that main.py imports from core.aws_service
if grep -q "from core.aws_service import aws_service" caseapp/backend/main.py; then
    echo -e "${GREEN}  ✅ PASS${NC} main.py imports from core.aws_service"
else
    echo -e "${RED}  ❌ FAIL${NC} main.py has incorrect import"
    exit 1
fi

# Test 4: Docker Build Test (optional - only if Docker is running)
echo ""
echo -e "${BLUE}[TEST 4]${NC} Docker Build Test (optional)"

if docker info >/dev/null 2>&1; then
    echo -e "${BLUE}  ℹ️  INFO${NC} Docker is running, testing build..."
    
    cd caseapp
    if docker build -t courtcase-test:latest . >/dev/null 2>&1; then
        echo -e "${GREEN}  ✅ PASS${NC} Docker build successful"
        
        # Clean up test image
        docker rmi courtcase-test:latest >/dev/null 2>&1 || true
    else
        echo -e "${RED}  ❌ FAIL${NC} Docker build failed"
        cd ..
        exit 1
    fi
    cd ..
else
    echo -e "${YELLOW}  ⚠️  SKIP${NC} Docker not running (not critical)"
fi

# Test 5: Check for Secrets in Secrets Manager
echo ""
echo -e "${BLUE}[TEST 5]${NC} AWS Secrets Check"

if AWS_PAGER="" aws secretsmanager describe-secret --secret-id dockerhub-credentials >/dev/null 2>&1; then
    echo -e "${GREEN}  ✅ PASS${NC} dockerhub-credentials secret exists"
else
    echo -e "${RED}  ❌ FAIL${NC} dockerhub-credentials secret not found"
    echo -e "${BLUE}  ℹ️  INFO${NC} Create with: aws secretsmanager create-secret --name dockerhub-credentials --secret-string '{\"username\":\"<user>\",\"password\":\"<token>\"}'"
    exit 1
fi

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
echo "=========================================="
echo ""
echo "Ready to push and deploy!"
echo ""
echo "Next steps:"
echo "  1. git add -A"
echo "  2. git commit -m \"your message\""
echo "  3. git push origin main"
echo "  4. Ask user permission to trigger deployment"
echo ""
