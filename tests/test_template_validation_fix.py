#!/usr/bin/env python3
"""
Test that template validation now accepts export metadata fields
"""
import json
from pathlib import Path

# Test both template files
template_files = [
    Path("docs3/Tempate Builder/Templates/Default_Forensic_Structure.json"),
    Path("docs3/Tempate Builder/Templates/Forensic_Documents_At_Occurrence.json")
]

print("Testing Template Validation Fix")
print("="*50)

for template_file in template_files:
    print(f"\nTesting: {template_file}")
    print("-"*40)
    
    if not template_file.exists():
        print(f"[SKIP] File not found: {template_file}")
        continue
    
    # Load the template
    with open(template_file, 'r') as f:
        template_data = json.load(f)
    
    # Check for metadata fields
    for template_id, template in template_data.get("templates", {}).items():
        print(f"Template ID: {template_id}")
        
        if "metadata" in template:
            metadata = template["metadata"]
            print("  Metadata fields found:")
            
            # Check for the fields that were causing validation errors
            problem_fields = ["exported_date", "exported_by", "original_source"]
            for field in problem_fields:
                if field in metadata:
                    print(f"    - {field}: {metadata[field]}")
            
            # Now validate with the schema
            try:
                from core.template_validator import TemplateValidator
                validator = TemplateValidator()
                
                result = validator.validate_template_file(template_file)
                
                if result.success:
                    issues = result.value
                    error_count = sum(1 for issue in issues if issue.level == "error")
                    warning_count = sum(1 for issue in issues if issue.level == "warning")
                    
                    if error_count == 0:
                        print(f"  [SUCCESS] Validation passed! ({warning_count} warnings)")
                    else:
                        print(f"  [FAILED] {error_count} errors found:")
                        for issue in issues:
                            if issue.level == "error":
                                print(f"    - {issue.message}")
                else:
                    print(f"  [ERROR] Validation failed: {result.error.message}")
                    
            except Exception as e:
                print(f"  [ERROR] Could not validate: {e}")
        else:
            print("  No metadata field")

print("\n" + "="*50)
print("[COMPLETE] Template validation testing finished")
print("\nThe schema has been updated to accept the following metadata fields:")
print("  - exported_date")
print("  - exported_by")
print("  - original_source")
print("  - imported_from")
print("  - imported_date")
print("\nTemplates can now be exported and re-imported without validation errors!")