// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import os
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime

class BadgeSchemaValidator:
    def __init__(self):
        self.required_base_fields = ['schemaVersion', 'label', 'message', 'color']
        self.valid_colors = [
            'brightgreen', 'green', 'yellowgreen', 'yellow', 'orange', 'red',
            'lightgrey', 'blue', 'success', 'important', 'critical', 'informational',
            'inactive', 'blueviolet', 'ff69b4', '9cf'
        ]
        self.valid_schema_versions = ['1']

    def validate_badge_file(self, filepath: str) -> Dict[str, Any]:
        """Validate a single badge JSON file"""
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'file': filepath
        }

        if not os.path.exists(filepath):
            result['errors'].append(f"File not found: {filepath}")
            return result

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            result['errors'].append(f"Invalid JSON: {str(e)}")
            return result
        except Exception as e:
            result['errors'].append(f"Error reading file: {str(e)}")
            return result

        # Validate required fields
        missing_fields = []
        for field in self.required_base_fields:
            if field not in data:
                missing_fields.append(field)

        if missing_fields:
            result['errors'].append(f"Missing required fields: {', '.join(missing_fields)}")

        # Validate schema version
        if 'schemaVersion' in data:
            if data['schemaVersion'] not in self.valid_schema_versions:
                result['errors'].append(f"Invalid schema version: {data['schemaVersion']}")

        # Validate color
        if 'color' in data:
            color = data['color'].lower()
            if not (color in self.valid_colors or self._is_valid_hex_color(color)):
                result['warnings'].append(f"Unusual color value: {data['color']}")

        # Validate message format
        if 'message' in data:
            if not isinstance(data['message'], str) or len(data['message']) == 0:
                result['errors'].append("Message must be a non-empty string")
            elif len(data['message']) > 200:
                result['warnings'].append("Message is quite long (>200 chars)")

        # Validate label format
        if 'label' in data:
            if not isinstance(data['label'], str) or len(data['label']) == 0:
                result['errors'].append("Label must be a non-empty string")

        # Check for extra fields (informational)
        extra_fields = set(data.keys()) - set(self.required_base_fields) - {'logoSvg', 'namedLogo', 'logoColor', 'logoWidth', 'style', 'labelColor'}
        if extra_fields:
            result['warnings'].append(f"Unexpected fields: {', '.join(extra_fields)}")

        result['valid'] = len(result['errors']) == 0
        return result

    def _is_valid_hex_color(self, color: str) -> bool:
        """Check if color is a valid hex color code"""
        if color.startswith('#'):
            color = color[1:]
        return len(color) in [3, 6] and all(c in '0123456789abcdefABCDEF' for c in color)

    def validate_directory(self, badges_dir: str) -> Dict[str, Any]:
        """Validate all badge JSON files in a directory"""
        results = {
            'total_files': 0,
            'valid_files': 0,
            'invalid_files': 0,
            'files': [],
            'summary': {
                'errors': 0,
                'warnings': 0
            }
        }

        if not os.path.exists(badges_dir):
            results['files'].append({
                'valid': False,
                'errors': [f"Directory not found: {badges_dir}"],
                'warnings': [],
                'file': badges_dir
            })
            return results

        json_files = [f for f in os.listdir(badges_dir) if f.endswith('.json')]
        results['total_files'] = len(json_files)

        for filename in sorted(json_files):
            filepath = os.path.join(badges_dir, filename)
            file_result = self.validate_badge_file(filepath)
            results['files'].append(file_result)

            if file_result['valid']:
                results['valid_files'] += 1
            else:
                results['invalid_files'] += 1

            results['summary']['errors'] += len(file_result['errors'])
            results['summary']['warnings'] += len(file_result['warnings'])

        return results

    def generate_report(self, validation_results: Dict[str, Any], output_format: str = 'text') -> str:
        """Generate a validation report"""
        if output_format == 'json':
            return json.dumps(validation_results, indent=2)

        # Text format
        report_lines = []
        report_lines.append("Badge Validation Report")
        report_lines.append("=" * 40)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")

        summary = validation_results['summary']
        report_lines.append(f"Total files: {validation_results['total_files']}")
        report_lines.append(f"Valid files: {validation_results['valid_files']}")
        report_lines.append(f"Invalid files: {validation_results['invalid_files']}")
        report_lines.append(f"Total errors: {summary['errors']}")
        report_lines.append(f"Total warnings: {summary['warnings']}")
        report_lines.append("")

        # File details
        for file_result in validation_results['files']:
            filename = os.path.basename(file_result['file'])
            status = "✓ VALID" if file_result['valid'] else "✗ INVALID"
            report_lines.append(f"{filename}: {status}")

            if file_result['errors']:
                for error in file_result['errors']:
                    report_lines.append(f"  ERROR: {error}")

            if file_result['warnings']:
                for warning in file_result['warnings']:
                    report_lines.append(f"  WARNING: {warning}")

            report_lines.append("")

        return "\n".join(report_lines)

def main():
    validator = BadgeSchemaValidator()

    # Default badges directory
    badges_dir = os.path.join('.github', 'badges')

    # Allow override via command line
    if len(sys.argv) > 1:
        badges_dir = sys.argv[1]

    print(f"Validating badges in: {badges_dir}")

    results = validator.validate_directory(badges_dir)
    report = validator.generate_report(results)

    print(report)

    # Exit with error code if any files are invalid
    if results['invalid_files'] > 0:
        sys.exit(1)
    else:
        print("All badge files are valid!")
        sys.exit(0)

if __name__ == "__main__":
    main()
