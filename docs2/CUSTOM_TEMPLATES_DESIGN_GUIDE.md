# Custom Templates Design Guide: Avoiding Phase 3 Issues

*Created: August 25, 2024*

## Executive Summary

This document provides architectural guidance for implementing a new custom templates feature while avoiding the security vulnerabilities, code duplication, and maintenance issues that led to the Phase 3 refactor. The original custom templates system was removed due to critical path sanitization inconsistencies and dead code accumulation. This guide ensures future implementations are secure, maintainable, and architecturally sound from the start.

---

## Lessons Learned from Phase 3

### What Went Wrong

1. **Dual Path Sanitization**: Created two different sanitizers with different security postures
2. **Dead Code Accumulation**: UI removal left backend code orphaned and unused
3. **Security Inconsistency**: Basic sanitizer missed critical attack vectors
4. **Maintenance Burden**: Two systems required synchronization and parallel updates
5. **Architecture Drift**: Feature evolved independently rather than integrating with existing systems

### Security Vulnerabilities That Must Be Avoided

1. **Path Traversal Attacks**: `../../../etc/passwd` bypassing basic sanitization
2. **Windows Reserved Names**: `CON.txt`, `PRN.doc` causing system issues  
3. **Control Character Injection**: Null bytes and Unicode control sequences
4. **Unicode Normalization Attacks**: Right-to-left overrides hiding file extensions
5. **Cross-Platform Incompatibility**: Platform-specific path limitations

---

## Architectural Principles for New Custom Templates

### 1. **Single Source of Truth for Path Sanitization**

**✅ REQUIRED: Use Existing Secure Infrastructure**
```python
# ALWAYS use the proven, secure sanitizer
from core.path_utils import PathSanitizer

def build_custom_path(template_parts: List[str]) -> Path:
    sanitized_parts = []
    for part in template_parts:
        # Use the existing, comprehensive sanitizer
        safe_part = PathSanitizer.sanitize_component(part)
        sanitized_parts.append(safe_part)
    return Path(*sanitized_parts)
```

**❌ NEVER: Create New Sanitization Logic**
```python
# NEVER DO THIS - creates dual system vulnerabilities
def custom_sanitize(text: str) -> str:
    # Custom logic creates security gaps and maintenance burden
    return text.replace('<', '_').replace('>', '_')
```

### 2. **Integration Over Duplication**

**✅ REQUIRED: Extend Existing Systems**
```python
class CustomTemplateBuilder:
    """Extends ForensicPathBuilder for custom templates"""
    
    def __init__(self):
        self.forensic_builder = ForensicPathBuilder()
    
    def build_from_template(self, template: CustomTemplate, form_data: FormData) -> Path:
        # Leverage existing secure path building
        base_path = self.forensic_builder.build_relative_path(form_data)
        
        # Add custom template logic using secure components
        custom_parts = self._process_template_parts(template.parts, form_data)
        
        # Always use secure sanitization
        sanitized_parts = [
            PathSanitizer.sanitize_component(part) 
            for part in custom_parts
        ]
        
        return base_path / Path(*sanitized_parts)
```

**❌ NEVER: Duplicate Core Logic**
```python
# NEVER DO THIS - duplicates sanitization and path building logic
class CustomTemplateBuilder:
    def build_custom_path(self, template, form_data):
        # Duplicated logic creates maintenance burden and drift risk
        parts = []
        for part in template.levels:
            sanitized = part.replace('<', '_')  # Insecure duplication
            parts.append(sanitized)
        return Path(*parts)
```

### 3. **Secure Template Processing**

**✅ REQUIRED: Validate Template Input**
```python
@dataclass
class CustomTemplate:
    """Secure custom template with validation"""
    name: str
    description: str
    template_parts: List[str]
    
    def __post_init__(self):
        # Validate template parts for security
        for part in self.template_parts:
            self._validate_template_part(part)
    
    def _validate_template_part(self, part: str):
        """Validate template part for security issues"""
        
        # Check for path traversal attempts
        if '..' in part or '/' in part or '\\' in part:
            raise ValueError(f"Template part contains path traversal: {part}")
        
        # Check for control characters
        if any(ord(c) < 32 for c in part):
            raise ValueError(f"Template part contains control characters: {part}")
        
        # Check for reserved patterns
        reserved_patterns = ['<script', 'javascript:', '${', '#{']
        if any(pattern in part.lower() for pattern in reserved_patterns):
            raise ValueError(f"Template part contains reserved pattern: {part}")

    def build_path_safely(self, form_data: FormData) -> Path:
        """Build path using secure, existing infrastructure"""
        # Process template variables
        processed_parts = []
        format_dict = self._build_format_dict(form_data)
        
        for template_part in self.template_parts:
            try:
                # Process template variables safely
                processed = template_part.format(**format_dict)
            except KeyError as e:
                # Handle missing variables gracefully
                processed = template_part  # Use literal if variable missing
            
            # ALWAYS use secure sanitization
            safe_part = PathSanitizer.sanitize_component(processed)
            if safe_part:  # Only add non-empty parts
                processed_parts.append(safe_part)
        
        return Path(*processed_parts) if processed_parts else Path('default')
    
    def _build_format_dict(self, form_data: FormData) -> Dict[str, str]:
        """Build format dictionary using existing, proven logic"""
        # Reuse the proven format dictionary from ForensicPathBuilder
        # This prevents duplication and ensures consistency
        return {
            'occurrence_number': form_data.occurrence_number or '',
            'business_name': form_data.business_name or '',
            'location_address': form_data.location_address or '',
            'technician_name': form_data.technician_name or '',
            'badge_number': form_data.badge_number or '',
            # Add new template-specific fields as needed
            'custom_field_1': getattr(form_data, 'custom_field_1', ''),
            'custom_field_2': getattr(form_data, 'custom_field_2', ''),
        }
```

### 4. **Dead Code Prevention Strategy**

**✅ REQUIRED: Tight UI-Backend Coupling**
```python
# UI removal should automatically trigger backend cleanup
class CustomTemplateManager:
    """Manages custom templates with usage tracking"""
    
    def __init__(self):
        self.active_templates: Dict[str, CustomTemplate] = {}
        self.usage_tracker = TemplateUsageTracker()
    
    def register_ui_component(self, component_id: str, template_id: str):
        """Register UI component using a template"""
        self.usage_tracker.register_usage(component_id, template_id)
    
    def unregister_ui_component(self, component_id: str):
        """Unregister UI component and check for dead templates"""
        removed_templates = self.usage_tracker.unregister_usage(component_id)
        
        # Automatically clean up unused templates
        for template_id in removed_templates:
            if not self.usage_tracker.has_active_usage(template_id):
                self._archive_unused_template(template_id)
                logger.info(f"Archived unused template: {template_id}")
    
    def _archive_unused_template(self, template_id: str):
        """Archive unused template to prevent dead code"""
        if template_id in self.active_templates:
            # Move to archive rather than delete (for recovery)
            archived_template = self.active_templates.pop(template_id)
            self._save_to_archive(template_id, archived_template)
```

**✅ REQUIRED: Usage Validation in CI/CD**
```python
# Add to test suite - prevents dead code deployment
class TestTemplateUsage:
    """Test that all template code has active usage"""
    
    def test_no_orphaned_template_code(self):
        """Ensure all template classes have active UI references"""
        
        # Scan for template-related classes
        template_classes = self._find_template_classes()
        
        # Scan UI code for template usage
        ui_references = self._find_ui_template_references()
        
        # Verify every template class is referenced
        orphaned_classes = template_classes - ui_references
        
        assert not orphaned_classes, f"Orphaned template classes detected: {orphaned_classes}"
        
    def test_template_methods_have_callers(self):
        """Ensure all template methods are actually called"""
        
        # Use static analysis to find unused methods
        unused_methods = self._analyze_template_method_usage()
        
        assert not unused_methods, f"Unused template methods detected: {unused_methods}"
```

---

## Secure Implementation Architecture

### Recommended Component Structure

```python
# Secure, maintainable custom templates architecture

class CustomTemplateEngine:
    """Main engine for custom template processing"""
    
    def __init__(self):
        # Use existing, proven components
        self.path_sanitizer = PathSanitizer()
        self.forensic_builder = ForensicPathBuilder()
        self.validator = TemplateValidator()
    
    def process_template(self, template: CustomTemplate, form_data: FormData) -> Path:
        """Process template using secure, existing infrastructure"""
        
        # 1. Validate template security
        self.validator.validate_template_security(template)
        
        # 2. Build base path using proven forensic system
        base_path = self.forensic_builder.build_relative_path(form_data)
        
        # 3. Process custom template parts securely
        custom_parts = self._process_custom_parts(template, form_data)
        
        # 4. Combine using secure path operations
        return self._combine_paths_securely(base_path, custom_parts)
    
    def _process_custom_parts(self, template: CustomTemplate, form_data: FormData) -> List[str]:
        """Process custom template parts with security validation"""
        processed_parts = []
        
        for part in template.template_parts:
            # Process template variables
            processed = self._substitute_variables(part, form_data)
            
            # Apply secure sanitization (single source of truth)
            sanitized = self.path_sanitizer.sanitize_component(processed)
            
            if sanitized:  # Only include non-empty parts
                processed_parts.append(sanitized)
        
        return processed_parts
    
    def _combine_paths_securely(self, base: Path, custom_parts: List[str]) -> Path:
        """Combine paths with security validation"""
        
        # Build combined path
        combined = base
        for part in custom_parts:
            combined = combined / part
        
        # Validate final path doesn't escape boundaries
        if str(combined).count('..') > 0:
            raise SecurityError("Template resulted in path traversal")
        
        return combined

class TemplateValidator:
    """Validates template security and structure"""
    
    FORBIDDEN_PATTERNS = [
        r'\.\.',           # Path traversal
        r'[<>:"|?*]',      # Invalid filename characters  
        r'[\x00-\x1f]',    # Control characters
        r'\${.*?}',        # Code injection patterns
        r'#{.*?}',         # Code injection patterns
        r'javascript:',    # Script injection
        r'<script',        # HTML injection
    ]
    
    def validate_template_security(self, template: CustomTemplate):
        """Validate template for security issues"""
        
        for part in template.template_parts:
            for pattern in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, part, re.IGNORECASE):
                    raise SecurityError(f"Template contains forbidden pattern: {pattern} in {part}")
        
        # Validate reasonable limits
        if len(template.template_parts) > 20:
            raise ValidationError("Template has too many parts (max 20)")
        
        total_length = sum(len(part) for part in template.template_parts)
        if total_length > 1000:
            raise ValidationError("Template total length exceeds 1000 characters")

class TemplateUsageTracker:
    """Tracks template usage to prevent dead code"""
    
    def __init__(self):
        self.usage_map: Dict[str, Set[str]] = {}  # template_id -> set of component_ids
        
    def register_usage(self, component_id: str, template_id: str):
        """Register that a UI component uses a template"""
        if template_id not in self.usage_map:
            self.usage_map[template_id] = set()
        self.usage_map[template_id].add(component_id)
    
    def unregister_usage(self, component_id: str) -> List[str]:
        """Unregister component and return unused templates"""
        unused_templates = []
        
        for template_id, component_set in self.usage_map.items():
            if component_id in component_set:
                component_set.remove(component_id)
                
                # If no more components use this template, it's unused
                if not component_set:
                    unused_templates.append(template_id)
        
        return unused_templates
    
    def has_active_usage(self, template_id: str) -> bool:
        """Check if template has any active usage"""
        return bool(self.usage_map.get(template_id))
```

---

## Security-First Development Process

### Pre-Implementation Security Review

Before implementing any custom template feature:

1. **Threat Model the Feature**
   - Identify all input sources (user templates, form data)
   - Map data flow from input to filesystem
   - Identify attack surfaces and mitigation strategies

2. **Security Requirements Definition**
   - Path sanitization requirements
   - Input validation requirements  
   - Output encoding requirements
   - Access control requirements

3. **Architecture Security Review**
   - Ensure single sanitization system
   - Verify integration with existing secure components
   - Validate no duplication of security-critical code

### Development Security Practices

```python
# Security-first template development checklist

class SecureTemplateImplementation:
    """Example of security-first template implementation"""
    
    def __init__(self):
        # ✅ SECURITY: Use existing, audited components
        self.sanitizer = PathSanitizer()
        self.validator = TemplateValidator()
    
    def create_template(self, user_input: Dict[str, Any]) -> CustomTemplate:
        """Create template with security validation"""
        
        # ✅ SECURITY: Validate all inputs immediately
        self._validate_user_input(user_input)
        
        # ✅ SECURITY: Sanitize template parts before storage
        sanitized_parts = [
            self.sanitizer.sanitize_component(part)
            for part in user_input.get('template_parts', [])
        ]
        
        # ✅ SECURITY: Create validated template object
        template = CustomTemplate(
            name=self.sanitizer.sanitize_component(user_input['name']),
            description=user_input.get('description', '')[:500],  # Limit length
            template_parts=sanitized_parts
        )
        
        # ✅ SECURITY: Final validation
        self.validator.validate_template_security(template)
        
        return template
    
    def _validate_user_input(self, user_input: Dict[str, Any]):
        """Validate user input for security issues"""
        
        # Check required fields
        if 'name' not in user_input:
            raise ValidationError("Template name is required")
        
        if 'template_parts' not in user_input:
            raise ValidationError("Template parts are required")
        
        # Validate data types
        if not isinstance(user_input['template_parts'], list):
            raise ValidationError("Template parts must be a list")
        
        # Check for obvious attack patterns
        dangerous_content = str(user_input).lower()
        if any(pattern in dangerous_content for pattern in ['<script', 'javascript:', '${', '../']):
            raise SecurityError("Template contains potentially dangerous content")
```

### Testing Security Requirements

```python
class TestCustomTemplateSecurity:
    """Comprehensive security tests for custom templates"""
    
    def test_path_traversal_prevention(self):
        """Test that path traversal attacks are prevented"""
        malicious_templates = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",  
            "normal/../../../etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2f",  # URL encoded
        ]
        
        for malicious_input in malicious_templates:
            template = CustomTemplate(
                name="test",
                description="test", 
                template_parts=[malicious_input]
            )
            
            # Should not contain parent directory references
            result_path = template.build_path_safely(FormData())
            assert '..' not in str(result_path), f"Path traversal not prevented: {result_path}"
    
    def test_windows_reserved_names(self):
        """Test that Windows reserved names are handled"""
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'LPT1']
        
        for reserved in reserved_names:
            template = CustomTemplate(
                name="test",
                description="test",
                template_parts=[reserved]
            )
            
            result_path = template.build_path_safely(FormData())
            
            # Should be prefixed to make safe
            assert str(result_path) != reserved, f"Reserved name not handled: {reserved}"
            assert f"_{reserved}" in str(result_path), f"Reserved name not properly prefixed: {result_path}"
    
    def test_control_character_removal(self):
        """Test that control characters are removed"""
        control_chars = [
            "file\x00name",     # Null byte
            "file\x1fname",     # Unit separator 
            "file\x08name",     # Backspace
            "file\x0aname",     # Line feed
        ]
        
        for malicious_input in control_chars:
            template = CustomTemplate(
                name="test",
                description="test",
                template_parts=[malicious_input]
            )
            
            result_path = template.build_path_safely(FormData())
            result_str = str(result_path)
            
            # Should not contain control characters
            assert not any(ord(c) < 32 for c in result_str), f"Control characters not removed: {repr(result_str)}"
    
    def test_single_sanitization_system(self):
        """Test that only PathSanitizer is used (no duplication)"""
        
        # This test ensures we don't recreate the Phase 3 problem
        template = CustomTemplate(
            name="test", 
            description="test",
            template_parts=["file<>name:test|file?.txt"]
        )
        
        result_path = template.build_path_safely(FormData())
        
        # Should match PathSanitizer output exactly
        expected = PathSanitizer.sanitize_component("file<>name:test|file?.txt")
        assert expected in str(result_path), "Not using PathSanitizer consistently"
```

---

## Monitoring and Maintenance

### Runtime Security Monitoring

```python
class TemplateSecurityMonitor:
    """Monitor template usage for security issues"""
    
    def __init__(self):
        self.security_logger = logging.getLogger('template_security')
        self.metrics = SecurityMetrics()
    
    def log_template_creation(self, template: CustomTemplate, user_id: str):
        """Log template creation for security auditing"""
        
        self.security_logger.info({
            'event': 'template_created',
            'user_id': user_id,
            'template_name': template.name,
            'template_parts_count': len(template.template_parts),
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Check for suspicious patterns
        self._check_suspicious_patterns(template, user_id)
    
    def _check_suspicious_patterns(self, template: CustomTemplate, user_id: str):
        """Check for suspicious patterns in templates"""
        
        suspicious_indicators = [
            (r'\.{2,}', 'multiple_dots'),
            (r'[<>:"|?*]{3,}', 'multiple_invalid_chars'), 
            (r'(admin|root|system)', 'privileged_terms'),
            (r'[a-f0-9]{32}', 'potential_hash'),
        ]
        
        for part in template.template_parts:
            for pattern, indicator in suspicious_indicators:
                if re.search(pattern, part, re.IGNORECASE):
                    self.security_logger.warning({
                        'event': 'suspicious_template_pattern',
                        'user_id': user_id,
                        'template_name': template.name,
                        'indicator': indicator,
                        'pattern': pattern,
                        'content': part[:100]  # Truncate for logging
                    })
```

### Dead Code Detection

```python
class DeadCodeDetector:
    """Detect and prevent dead code accumulation"""
    
    def __init__(self):
        self.usage_tracker = TemplateUsageTracker()
        self.code_analyzer = StaticCodeAnalyzer()
    
    def scan_for_dead_templates(self) -> List[str]:
        """Scan for templates that are no longer used"""
        
        # Get all defined templates
        all_templates = self._find_all_template_definitions()
        
        # Get templates referenced in UI
        ui_references = self._scan_ui_for_template_usage()
        
        # Find templates with no references
        dead_templates = all_templates - ui_references
        
        return dead_templates
    
    def generate_cleanup_report(self) -> str:
        """Generate report of code that can be safely removed"""
        
        dead_templates = self.scan_for_dead_templates()
        unused_methods = self.code_analyzer.find_unused_template_methods()
        
        report = f"""
# Dead Code Cleanup Report
Generated: {datetime.now().isoformat()}

## Unused Templates ({len(dead_templates)})
{chr(10).join(f"- {template}" for template in dead_templates)}

## Unused Methods ({len(unused_methods)})
{chr(10).join(f"- {method}" for method in unused_methods)}

## Recommended Actions
1. Archive unused templates to legacy/
2. Remove unused methods after verification
3. Update tests to reflect removal
4. Update documentation
"""
        
        return report
```

---

## Implementation Roadmap

### Phase 1: Security Foundation (Week 1)
- [ ] Implement `TemplateValidator` with comprehensive security checks
- [ ] Create `CustomTemplate` dataclass with built-in validation
- [ ] Write comprehensive security test suite
- [ ] Set up security monitoring and logging

### Phase 2: Core Template Engine (Week 2)
- [ ] Implement `CustomTemplateEngine` using existing secure components
- [ ] Create `TemplateUsageTracker` for dead code prevention
- [ ] Integrate with existing `ForensicPathBuilder` and `PathSanitizer`
- [ ] Write integration tests with existing systems

### Phase 3: UI Integration (Week 3)
- [ ] Design UI with tight backend coupling
- [ ] Implement usage registration/tracking in UI components
- [ ] Add template preview with security validation
- [ ] Create user-friendly error messages for security violations

### Phase 4: Monitoring and Maintenance (Week 4)
- [ ] Implement `TemplateSecurityMonitor` for runtime monitoring
- [ ] Create `DeadCodeDetector` for maintenance automation
- [ ] Set up automated security scanning in CI/CD
- [ ] Create maintenance documentation and runbooks

---

## Success Criteria

### Security Requirements
- [ ] Zero path traversal vulnerabilities
- [ ] All Windows reserved names handled safely
- [ ] Control characters filtered from all paths
- [ ] Unicode normalization attacks prevented
- [ ] Cross-platform path compatibility guaranteed

### Architecture Requirements  
- [ ] Single path sanitization system used throughout
- [ ] Zero duplication of security-critical code
- [ ] Full integration with existing secure components
- [ ] Usage tracking prevents dead code accumulation
- [ ] Automated testing validates security requirements

### Maintenance Requirements
- [ ] UI removal automatically triggers backend cleanup
- [ ] Static analysis detects unused template code
- [ ] Security monitoring logs all template operations
- [ ] Documentation reflects actual implementation
- [ ] Test suite validates security and functionality

---

## Conclusion

The Phase 3 refactor taught us that security vulnerabilities often arise from code duplication and architectural drift. By following this guide, future custom template implementations will:

1. **Reuse existing secure infrastructure** rather than duplicating sanitization logic
2. **Integrate tightly with UI components** to prevent dead code accumulation  
3. **Implement security-first development practices** with comprehensive validation
4. **Monitor and maintain security posture** through automated detection and logging

This approach transforms custom templates from a security risk into a secure, maintainable feature that enhances the application's capabilities without compromising its security foundation.