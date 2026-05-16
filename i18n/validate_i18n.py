#!/usr/bin/env python3
"""
RustChain i18n 验证脚本

验证 i18n JSON 文件的格式、结构和完整性。

用法:
    python i18n/validate_i18n.py
    
验证内容:
    1. JSON 格式有效性
    2. 必需的顶层键存在
    3. 错误消息分类完整性
    4. 至少包含 20 条用户-facing 错误消息
    5. UTF-8 编码
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple


# 必需的顶层键
REQUIRED_TOP_KEYS = ["locale", "language", "version", "errors", "messages"]

# 必需的错误分类
REQUIRED_ERROR_CATEGORIES = ["wallet", "miner", "network", "common"]

# 必需的消息分类
REQUIRED_MESSAGE_CATEGORIES = ["wallet", "miner"]

# 最小错误消息数量
MIN_ERROR_MESSAGES = 20


def count_messages(data: Dict[str, Any], category: str) -> int:
    """递归计算某类别下的消息数量"""
    count = 0
    if category in data:
        section = data[category]
        for key, value in section.items():
            if isinstance(value, str):
                count += 1
            elif isinstance(value, dict):
                count += count_messages(section, key)
    return count


def count_all_strings(data: Dict[str, Any]) -> int:
    """计算 JSON 中所有字符串值的数量"""
    count = 0
    for key, value in data.items():
        if key in ["locale", "language", "version", "description"]:
            continue
        if isinstance(value, str):
            count += 1
        elif isinstance(value, dict):
            count += count_all_strings(value)
    return count


def validate_json_structure(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """验证 JSON 结构完整性"""
    errors = []
    
    # 检查必需的顶层键
    for key in REQUIRED_TOP_KEYS:
        if key not in data:
            errors.append(f"缺少必需的顶层键：{key}")
    
    # 检查 errors 分类
    if "errors" in data:
        for category in REQUIRED_ERROR_CATEGORIES:
            if category not in data["errors"]:
                errors.append(f"errors 缺少必需的分类：{category}")
    
    # 检查 messages 分类
    if "messages" in data:
        for category in REQUIRED_MESSAGE_CATEGORIES:
            if category not in data["messages"]:
                errors.append(f"messages 缺少必需的分类：{category}")
    
    return len(errors) == 0, errors


def validate_locale_format(locale: str) -> bool:
    """验证语言代码格式 (如 zh-CN, en-US)"""
    import re
    pattern = r'^[a-z]{2}(-[A-Z]{2})?$'
    return bool(re.match(pattern, locale))


def validate_translation_file(filepath: Path) -> Tuple[bool, List[str]]:
    """验证单个翻译文件"""
    errors = []
    warnings = []
    
    # 检查文件存在
    if not filepath.exists():
        return False, [f"文件不存在：{filepath}"]
    
    # 检查 UTF-8 编码
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError as e:
        return False, [f"UTF-8 编码错误：{e}"]
    
    # 解析 JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, [f"JSON 格式错误：{e}"]
    
    # 验证结构
    valid, struct_errors = validate_json_structure(data)
    errors.extend(struct_errors)
    
    # 验证 locale 格式
    if "locale" in data:
        if not validate_locale_format(data["locale"]):
            warnings.append(f"locale 格式可能不正确：{data['locale']}")
    
    # 统计消息数量
    error_count = count_all_strings(data.get("errors", {}))
    message_count = count_all_strings(data.get("messages", {}))
    total_count = error_count + message_count
    
    print(f"  错误消息数量：{error_count}")
    print(f"  界面消息数量：{message_count}")
    print(f"  总计：{total_count}")
    
    if error_count < MIN_ERROR_MESSAGES:
        errors.append(f"错误消息数量不足：{error_count} < {MIN_ERROR_MESSAGES}")
    
    # 检查占位符格式
    placeholder_issues = check_placeholders(data, filepath.name)
    warnings.extend(placeholder_issues)
    
    return len(errors) == 0, errors, warnings


def check_placeholders(data: Dict[str, Any], filename: str) -> List[str]:
    """检查占位符格式一致性"""
    issues = []
    
    def check_value(value: str, path: str):
        if not isinstance(value, str):
            return
        # Keep this validation intentionally lightweight: translation files may
        # contain many languages and locale-specific punctuation, so this only
        # catches broken brace pairs without trying to parse Python format specs.
        if '{' in value and '}' not in value:
            issues.append(f"{filename}: {path} - 未闭合的占位符")
        if '}' in value and '{' not in value:
            issues.append(f"{filename}: {path} - 未闭合的占位符")
    
    def traverse(obj: Dict[str, Any], path: str = ""):
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key
            if isinstance(value, dict):
                traverse(value, current_path)
            elif isinstance(value, str):
                check_value(value, current_path)
    
    traverse(data)
    return issues


def main():
    """主验证函数"""
    print("=" * 60)
    print("RustChain i18n 验证工具")
    print("=" * 60)
    
    i18n_dir = Path(__file__).parent
    json_files = list(i18n_dir.glob("*.json"))
    
    if not json_files:
        print("\n❌ 错误：i18n 目录中没有找到 JSON 文件")
        sys.exit(1)
    
    print(f"\n找到 {len(json_files)} 个翻译文件:\n")
    
    all_valid = True
    all_warnings = []
    
    for json_file in json_files:
        print(f"\n验证：{json_file.name}")
        print("-" * 40)
        
        result = validate_translation_file(json_file)
        
        if len(result) == 2:
            valid, errors = result
            warnings = []
        else:
            valid, errors, warnings = result
        
        all_warnings.extend(warnings)
        
        if valid:
            print(f"  ✓ 验证通过")
        else:
            print(f"  ✗ 验证失败:")
            for error in errors:
                print(f"    - {error}")
            all_valid = False
    
    # 显示警告
    if all_warnings:
        print("\n⚠ 警告:")
        for warning in all_warnings:
            print(f"  - {warning}")
    
    # 总结
    print("\n" + "=" * 60)
    if all_valid:
        print("✓ 所有文件验证通过!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("✗ 验证失败，请修复上述错误")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
