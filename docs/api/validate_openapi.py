#!/usr/bin/env python3
"""
OpenAPI Schema Validator for RustChain API Specification

This script validates the OpenAPI 3.0 specification against:
1. YAML syntax correctness
2. OpenAPI 3.0 schema compliance
3. Required fields presence
4. Reference integrity ($ref resolution)
5. Response schema completeness

Usage:
    python validate_openapi.py [path/to/openapi.yaml]

Exit codes:
    0 - Validation passed
    1 - Validation failed
"""

import sys
import os
import json
from pathlib import Path

# Try to import required libraries
try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Install with: pip install pyyaml")
    sys.exit(1)


class OpenAPIValidator:
    """Validates OpenAPI 3.0 specifications."""
    
    REQUIRED_ROOT_FIELDS = ['openapi', 'info', 'paths']
    REQUIRED_INFO_FIELDS = ['title', 'version']
    REQUIRED_PATH_FIELDS = ['summary', 'responses']
    REQUIRED_RESPONSE_FIELDS = ['description']
    REQUIRED_COMPONENT_SCHEMA_FIELDS = ['type']
    
    def __init__(self, spec_path: str):
        self.spec_path = Path(spec_path)
        self.errors = []
        self.warnings = []
        self.spec = None
        
    def load_spec(self) -> bool:
        """Load and parse the OpenAPI specification."""
        if not self.spec_path.exists():
            self.errors.append(f"File not found: {self.spec_path}")
            return False
            
        try:
            with open(self.spec_path, 'r', encoding='utf-8') as f:
                self.spec = yaml.safe_load(f)
            return True
        except yaml.YAMLError as e:
            self.errors.append(f"YAML parsing error: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Failed to load spec: {e}")
            return False
    
    def validate_root(self) -> bool:
        """Validate root-level required fields."""
        if not isinstance(self.spec, dict):
            self.errors.append("Root must be a dictionary")
            return False
            
        # Check OpenAPI version
        openapi_version = self.spec.get('openapi', '')
        if not openapi_version.startswith('3.0'):
            self.errors.append(f"Unsupported OpenAPI version: {openapi_version}. Expected 3.0.x")
            
        # Check required fields
        for field in self.REQUIRED_ROOT_FIELDS:
            if field not in self.spec:
                self.errors.append(f"Missing required root field: {field}")
                
        # Validate info section
        info = self.spec.get('info', {})
        for field in self.REQUIRED_INFO_FIELDS:
            if field not in info:
                self.errors.append(f"Missing required info field: {field}")
                
        return len(self.errors) == 0
    
    def validate_paths(self) -> bool:
        """Validate path definitions."""
        paths = self.spec.get('paths', {})
        
        if not paths:
            self.warnings.append("No paths defined in specification")
            return True
            
        for path, path_item in paths.items():
            if not path.startswith('/'):
                self.errors.append(f"Path must start with '/': {path}")
                
            if not isinstance(path_item, dict):
                self.errors.append(f"Path item must be a dictionary: {path}")
                continue
                
            # Validate each HTTP method
            for method in ['get', 'post', 'put', 'patch', 'delete', 'options', 'head']:
                operation = path_item.get(method)
                if operation:
                    self._validate_operation(path, method, operation)
                    
        return len(self.errors) == 0
    
    def _validate_operation(self, path: str, method: str, operation: dict):
        """Validate a single operation."""
        if not isinstance(operation, dict):
            self.errors.append(f"Operation must be a dictionary: {method.upper()} {path}")
            return
            
        # Check required fields
        if 'summary' not in operation:
            self.warnings.append(f"Missing summary: {method.upper()} {path}")
            
        if 'responses' not in operation:
            self.errors.append(f"Missing responses: {method.upper()} {path}")
            return
            
        # Validate responses
        responses = operation.get('responses', {})
        if not responses:
            self.errors.append(f"No responses defined: {method.upper()} {path}")
        else:
            for status_code, response in responses.items():
                if not isinstance(response, dict):
                    self.errors.append(f"Invalid response format: {status_code} in {method.upper()} {path}")
                    continue
                if 'description' not in response:
                    self.errors.append(f"Missing description for response {status_code}: {method.upper()} {path}")
                    
        # Validate parameters
        params = operation.get('parameters', [])
        for param in params:
            if not isinstance(param, dict):
                continue
            if 'name' not in param:
                self.errors.append(f"Parameter missing 'name': {method.upper()} {path}")
            if 'in' not in param:
                self.errors.append(f"Parameter missing 'in': {method.upper()} {path}")
            elif param['in'] not in ['query', 'header', 'path', 'cookie']:
                self.errors.append(f"Invalid parameter location: {param['in']} in {method.upper()} {path}")
                
        # Validate requestBody
        request_body = operation.get('requestBody')
        if request_body:
            if 'content' not in request_body:
                self.errors.append(f"requestBody missing 'content': {method.upper()} {path}")
    
    def validate_components(self) -> bool:
        """Validate components section."""
        components = self.spec.get('components', {})
        
        # Validate schemas
        schemas = components.get('schemas', {})
        for name, schema in schemas.items():
            if not isinstance(schema, dict):
                self.errors.append(f"Schema must be a dictionary: {name}")
                continue
                
            # Check for type or $ref
            if 'type' not in schema and '$ref' not in schema and 'oneOf' not in schema and 'allOf' not in schema:
                self.warnings.append(f"Schema missing type or reference: {name}")
                
        # Validate security schemes
        security_schemes = components.get('securitySchemes', {})
        for name, scheme in security_schemes.items():
            if not isinstance(scheme, dict):
                self.errors.append(f"Security scheme must be a dictionary: {name}")
                continue
            if 'type' not in scheme:
                self.errors.append(f"Security scheme missing 'type': {name}")
                
        return len(self.errors) == 0
    
    def validate_references(self) -> bool:
        """Validate $ref references resolve correctly."""
        if not self.spec:
            return False
            
        # Collect all defined schemas
        defined_schemas = set()
        components = self.spec.get('components', {})
        schemas = components.get('schemas', {})
        for name in schemas.keys():
            defined_schemas.add(f"#/components/schemas/{name}")
            
        # Find all references
        refs = self._find_all_refs(self.spec)
        
        for ref in refs:
            if ref.startswith('#/components/schemas/'):
                if ref not in defined_schemas:
                    schema_name = ref.split('/')[-1]
                    self.errors.append(f"Undefined schema reference: {schema_name}")
                    
        return len(self.errors) == 0
    
    def _find_all_refs(self, obj, refs=None):
        """Recursively find all $ref values."""
        if refs is None:
            refs = []
            
        if isinstance(obj, dict):
            if '$ref' in obj:
                refs.append(obj['$ref'])
            for value in obj.values():
                self._find_all_refs(value, refs)
        elif isinstance(obj, list):
            for item in obj:
                self._find_all_refs(item, refs)
                
        return refs
    
    def validate_security(self) -> bool:
        """Validate security definitions and usage."""
        # Get defined security schemes
        defined_schemes = set()
        components = self.spec.get('components', {})
        security_schemes = components.get('securitySchemes', {})
        for name in security_schemes.keys():
            defined_schemes.add(name)
            
        # Check security usage in operations
        for path, path_item in self.spec.get('paths', {}).items():
            for method in ['get', 'post', 'put', 'patch', 'delete']:
                operation = path_item.get(method)
                if operation:
                    security = operation.get('security', [])
                    for sec_req in security:
                        if isinstance(sec_req, dict):
                            for scheme_name in sec_req.keys():
                                if scheme_name not in defined_schemes:
                                    self.errors.append(
                                        f"Undefined security scheme '{scheme_name}' used in {method.upper()} {path}"
                                    )
                                    
        return len(self.errors) == 0
    
    def validate(self) -> bool:
        """Run all validations."""
        print(f"Validating: {self.spec_path}")
        print("-" * 60)
        
        # Load spec
        print("Loading specification...")
        if not self.load_spec():
            self._print_results()
            return False
        print("✓ Specification loaded successfully")
        
        # Run validations
        validations = [
            ("Root structure", self.validate_root),
            ("Paths and operations", self.validate_paths),
            ("Components", self.validate_components),
            ("References", self.validate_references),
            ("Security", self.validate_security),
        ]
        
        all_passed = True
        for name, validator in validations:
            print(f"Validating {name}...")
            if validator():
                print(f"✓ {name} passed")
            else:
                print(f"✗ {name} failed")
                all_passed = False
                
        self._print_results()
        return all_passed
    
    def _print_results(self):
        """Print validation results."""
        print("\n" + "=" * 60)
        print("VALIDATION RESULTS")
        print("=" * 60)
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")
                
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")
                
        if not self.errors and not self.warnings:
            print("\n✅ No errors or warnings found!")
        elif not self.errors:
            print(f"\n✅ No errors found ({len(self.warnings)} warnings)")
            
        print("=" * 60)


def main():
    """Main entry point."""
    # Determine spec path
    if len(sys.argv) > 1:
        spec_path = sys.argv[1]
    else:
        # Default to docs/api/openapi.yaml relative to script
        script_dir = Path(__file__).parent
        spec_path = script_dir / 'openapi.yaml'
        
    # Run validation
    validator = OpenAPIValidator(str(spec_path))
    success = validator.validate()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
