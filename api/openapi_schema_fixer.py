"""
Fix OpenAPI balance path schema duplicate key issue
"""
import json
import yaml
from typing import Dict, List, Any
from pathlib import Path


class OpenAPISchemaFixer:
    """Fix duplicate keys in OpenAPI schemas"""
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.errors = []
    
    def fix_duplicate_keys(self, schema: Dict) -> Dict:
        """Remove duplicate keys in schema"""
        if not isinstance(schema, dict):
            return schema
        
        fixed = {}
        seen_keys = {}
        
        for key, value in schema.items():
            if key in seen_keys:
                if self.strict_mode:
                    self.errors.append(f"Duplicate key: {key}")
                    # Keep the last occurrence
                    fixed[key] = self._fix_nested(value)
            else:
                seen_keys[key] = True
                fixed[key] = self._fix_nested(value)
        
        return fixed
    
    def _fix_nested(self, obj: Any) -> Any:
        """Recursively fix nested objects"""
        if isinstance(obj, dict):
            return self.fix_duplicate_keys(obj)
        elif isinstance(obj, list):
            return [self._fix_nested(item) for item in obj]
        else:
            return obj
    
    def fix_balance_endpoint(self, spec: Dict) -> Dict:
        """Specifically fix /balance endpoint schema"""
        if 'paths' not in spec:
            return spec
        
        balance_path = None
        for path in spec['paths']:
            if 'balance' in path:
                balance_path = path
                break
        
        if not balance_path:
            self.errors.append("No balance path found")
            return spec
        
        # Fix the balance path schema
        balance_spec = spec['paths'][balance_path]
        
        # Check for duplicate 'schema' keys
        if 'get' in balance_spec:
            get_spec = balance_spec['get']
            if 'responses' in get_spec:
                responses = get_spec['responses']
                if '200' in responses:
                    response_200 = responses['200']
                    if 'content' in response_200:
                        content = response_200['content']
                        if 'application/json' in content:
                            schema = content['application/json'].get('schema', {})
                            # Fix duplicate keys
                            fixed_schema = self.fix_duplicate_keys(schema)
                            content['application/json']['schema'] = fixed_schema
        
        return spec
    
    def validate_schema(self, spec: Dict) -> bool:
        """Validate OpenAPI schema"""
        try:
            # Check for required fields
            if 'openapi' not in spec:
                self.errors.append("Missing 'openapi' field")
                return False
            
            if 'paths' not in spec:
                self.errors.append("Missing 'paths' field")
                return False
            
            # Validate all paths
            for path, path_spec in spec['paths'].items():
                if not isinstance(path_spec, dict):
                    self.errors.append(f"Invalid path spec: {path}")
                    return False
            
            return True
        except Exception as e:
            self.errors.append(f"Validation error: {e}")
            return False
    
    def save_fixed_schema(self, spec: Dict, output_path: str):
        """Save fixed schema to file"""
        output = Path(output_path)
        
        if output.suffix in ['.yaml', '.yml']:
            with output.open('w') as f:
                yaml.dump(spec, f, default_flow_style=False)
        else:
            with output.open('w') as f:
                json.dump(spec, f, indent=2)
        
        print(f"Fixed schema saved to {output_path}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OpenAPI Schema Fixer')
    parser.add_argument('--input', type=str, help='Input OpenAPI spec file')
    parser.add_argument('--output', type=str, help='Output file')
    parser.add_argument('--strict', action='store_true', help='Enable strict mode')
    
    args = parser.parse_args()
    
    if not args.input:
        print("Please provide --input <file>")
        return
    
    fixer = OpenAPISchemaFixer(strict_mode=args.strict)
    
    # Load spec
    input_path = Path(args.input)
    with input_path.open('r') as f:
        if input_path.suffix in ['.yaml', '.yml']:
            spec = yaml.safe_load(f)
        else:
            spec = json.load(f)
    
    print(f"Loaded spec from {args.input}")
    
    # Fix duplicate keys
    print("Fixing duplicate keys...")
    fixed_spec = fixer.fix_duplicate_keys(spec)
    
    # Specifically fix balance endpoint
    print("Fixing balance endpoint...")
    fixed_spec = fixer.fix_balance_endpoint(fixed_spec)
    
    # Validate
    print("Validating...")
    if fixer.validate_schema(fixed_spec):
        print("✅ Schema is valid")
    else:
        print("❌ Schema has errors:")
        for error in fixer.errors:
            print(f"  - {error}")
    
    # Save
    if args.output:
        fixer.save_fixed_schema(fixed_spec, args.output)
    else:
        print("
Fixed schema:")
        print(json.dumps(fixed_spec, indent=2))


if __name__ == '__main__':
    main()
