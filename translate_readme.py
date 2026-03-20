# SPDX-License-Identifier: MIT

import os
import re
import json
from typing import Dict, List, Set, Optional
from pathlib import Path

class ReadmeTranslationValidator:
    def __init__(self, base_readme_path: str = "README.md"):
        self.base_readme_path = base_readme_path
        self.base_sections = []
        self.translation_dir = "translations"

        # Language codes and names mapping
        self.languages = {
            'zh-CN': 'Chinese (Simplified)',
            'zh-TW': 'Chinese (Traditional)',
            'es': 'Spanish',
            'pt-BR': 'Portuguese',
            'ja': 'Japanese',
            'ko': 'Korean',
            'ru': 'Russian',
            'fr': 'French',
            'de': 'German',
            'ar': 'Arabic',
            'hi': 'Hindi',
            'tr': 'Turkish'
        }

    def extract_sections(self, content: str) -> List[str]:
        """Extract section headers from README content"""
        sections = []
        lines = content.split('\n')

        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                # Extract header level and text
                header_match = re.match(r'^(#+)\s*(.+)$', line)
                if header_match:
                    level = len(header_match.group(1))
                    text = header_match.group(2).strip()
                    sections.append(f"{'  ' * (level-1)}• {text}")

        return sections

    def load_base_readme(self) -> bool:
        """Load the base English README and extract its structure"""
        try:
            with open(self.base_readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.base_sections = self.extract_sections(content)
                return True
        except FileNotFoundError:
            print(f"❌ Base README not found: {self.base_readme_path}")
            return False
        except Exception as e:
            print(f"❌ Error reading base README: {e}")
            return False

    def validate_translation(self, lang_code: str, translation_path: str) -> Dict:
        """Validate a single translation file"""
        result = {
            'lang_code': lang_code,
            'lang_name': self.languages.get(lang_code, 'Unknown'),
            'file_exists': False,
            'sections': [],
            'missing_sections': [],
            'extra_sections': [],
            'formatting_issues': [],
            'word_count': 0,
            'score': 0
        }

        if not os.path.exists(translation_path):
            return result

        result['file_exists'] = True

        try:
            with open(translation_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract sections from translation
            trans_sections = self.extract_sections(content)
            result['sections'] = trans_sections
            result['word_count'] = len(content.split())

            # Compare with base sections structure
            base_headers = [s.split('• ')[1] if '• ' in s else s for s in self.base_sections]
            trans_headers = [s.split('• ')[1] if '• ' in s else s for s in trans_sections]

            # Find missing and extra sections
            base_set = set(base_headers)
            trans_set = set(trans_headers)

            result['missing_sections'] = list(base_set - trans_set)
            result['extra_sections'] = list(trans_set - base_set)

            # Check for formatting issues
            if not content.startswith('# '):
                result['formatting_issues'].append("Missing main title")

            if '<!-- SPDX-License-Identifier: MIT -->' not in content:
                result['formatting_issues'].append("Missing license header")

            # Calculate quality score
            section_score = max(0, 100 - len(result['missing_sections']) * 10)
            format_score = max(0, 100 - len(result['formatting_issues']) * 20)
            length_score = min(100, max(20, result['word_count'] / 10))

            result['score'] = int((section_score + format_score + length_score) / 3)

        except Exception as e:
            result['formatting_issues'].append(f"Error reading file: {e}")

        return result

    def scan_translations(self) -> List[Dict]:
        """Scan for all translation files and validate them"""
        results = []

        # Create translations directory if it doesn't exist
        Path(self.translation_dir).mkdir(exist_ok=True)

        for lang_code, lang_name in self.languages.items():
            translation_path = f"{self.translation_dir}/README_{lang_code}.md"
            result = self.validate_translation(lang_code, translation_path)
            results.append(result)

        return results

    def generate_report(self, results: List[Dict]) -> str:
        """Generate a comprehensive validation report"""
        report = []
        report.append("# README Translation Validation Report\n")

        # Summary statistics
        total_langs = len(results)
        completed = len([r for r in results if r['file_exists']])
        avg_score = sum(r['score'] for r in results if r['file_exists']) / max(1, completed)

        report.append(f"**Languages Total:** {total_langs}")
        report.append(f"**Translations Completed:** {completed}/{total_langs}")
        report.append(f"**Average Quality Score:** {avg_score:.1f}/100\n")

        # Detailed results
        report.append("## Translation Status\n")

        for result in sorted(results, key=lambda x: x['score'], reverse=True):
            status_icon = "✅" if result['file_exists'] else "⬜"
            score_badge = f"({result['score']}/100)" if result['file_exists'] else ""

            report.append(f"### {status_icon} {result['lang_name']} ({result['lang_code']}) {score_badge}")

            if result['file_exists']:
                report.append(f"- **Word Count:** {result['word_count']}")
                report.append(f"- **Sections:** {len(result['sections'])}")

                if result['missing_sections']:
                    report.append(f"- **Missing Sections:** {', '.join(result['missing_sections'])}")

                if result['formatting_issues']:
                    report.append(f"- **Issues:** {', '.join(result['formatting_issues'])}")

            else:
                report.append("- Status: Not started")

            report.append("")

        return '\n'.join(report)

    def create_template(self, lang_code: str) -> bool:
        """Create a translation template for a specific language"""
        if not self.base_sections:
            print("❌ Base README not loaded")
            return False

        template_path = f"{self.translation_dir}/README_{lang_code}.md"

        if os.path.exists(template_path):
            print(f"⚠️  Template already exists: {template_path}")
            return False

        try:
            # Read base README content
            with open(self.base_readme_path, 'r', encoding='utf-8') as f:
                base_content = f.read()

            # Create template with translation notes
            template_content = f"""<!-- SPDX-License-Identifier: MIT -->
<!-- Translation Template for {self.languages.get(lang_code, lang_code)} -->
<!-- Please translate all content below, keeping the same structure -->

{base_content}

<!--
Translation Notes:
- Keep all links functional
- Preserve code blocks and technical terms
- Maintain the same heading structure
- Update any language-specific examples if needed
-->
"""

            Path(self.translation_dir).mkdir(exist_ok=True)

            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(template_content)

            print(f"✅ Created translation template: {template_path}")
            return True

        except Exception as e:
            print(f"❌ Error creating template: {e}")
            return False

def main():
    validator = ReadmeTranslationValidator()

    print("🔍 README Translation Validator")
    print("=" * 40)

    # Load base README
    if not validator.load_base_readme():
        return

    print(f"✅ Loaded base README with {len(validator.base_sections)} sections\n")

    # Scan existing translations
    results = validator.scan_translations()

    # Generate and save report
    report = validator.generate_report(results)

    with open("translation_report.md", "w", encoding="utf-8") as f:
        f.write(report)

    print("📊 Translation Report:")
    print("-" * 20)
    print(report[:500] + "..." if len(report) > 500 else report)
    print(f"\n💾 Full report saved to: translation_report.md")

    # Offer to create templates
    incomplete = [r for r in results if not r['file_exists']]
    if incomplete:
        print(f"\n📝 Found {len(incomplete)} languages without translations")

        create_templates = input("Create translation templates? (y/N): ").lower().strip()
        if create_templates == 'y':
            for result in incomplete[:3]:  # Limit to first 3
                validator.create_template(result['lang_code'])

if __name__ == "__main__":
    main()
