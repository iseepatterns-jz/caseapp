#!/bin/bash
set -e

echo "🔍 Running AWS Infrastructure Validation..."
echo ""

# Read the template
TEMPLATE_PATH="caseapp/infrastructure/cdk.out/CourtCaseManagementStack.template.json"

if [ ! -f "$TEMPLATE_PATH" ]; then
    echo "❌ Template not found at $TEMPLATE_PATH"
    exit 1
fi

echo "✅ Template found: $TEMPLATE_PATH"
echo "📊 Template size: $(wc -c < "$TEMPLATE_PATH") bytes"
echo "📦 Resources: $(jq '.Resources | length' "$TEMPLATE_PATH")"
echo ""

# Note: The actual validation will be done via Kiro Powers
# This script just prepares the environment

echo "✅ Ready for validation"
echo ""
echo "Next steps:"
echo "1. Use kiroPowers to validate syntax with validate_cloudformation_template"
echo "2. Use kiroPowers to check compliance with check_cloudformation_template_compliance"
