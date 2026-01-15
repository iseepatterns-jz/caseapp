#!/usr/bin/env python3
import json

# Read the template
with open('caseapp/infrastructure/cdk.out/CourtCaseManagementStack.template.json', 'r') as f:
    template_content = f.read()

# Validate it's valid JSON
try:
    template_obj = json.loads(template_content)
    print(f"✅ Template is valid JSON")
    print(f"📊 Template size: {len(template_content)} characters")
    print(f"📦 Resources count: {len(template_obj.get('Resources', {}))}")
    
    # Save to a file for validation
    with open('template-for-validation.json', 'w') as out:
        out.write(template_content)
    print("✅ Template saved to template-for-validation.json")
    
except json.JSONDecodeError as e:
    print(f"❌ Template is not valid JSON: {e}")
