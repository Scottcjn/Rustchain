# RustChain i18n (国际化)

RustChain 用户界面错误消息的多语言翻译系统。

## 目录结构

```
i18n/
├── README.md          # 本文件
├── zh-CN.json         # 简体中文翻译
└── ...                # 其他语言（未来添加）
```

## 支持的语言

| 语言代码 | 语言名称 | 文件 |
|---------|---------|------|
| zh-CN | 简体中文 | zh-CN.json |

## 翻译范围

当前翻译覆盖以下用户界面路径的错误消息：

### 钱包 (wallet/)
- `rustchain_wallet_gui.py` - 图形界面钱包错误消息
- 网络错误处理与诊断
- 交易错误提示
- 余额查询错误

### 矿工 (miners/)
- `miners/windows/rustchain_windows_miner.py` - Windows 矿工客户端
- 硬件认证错误
- 纪元注册错误
- 指纹验证状态

## JSON 结构

```json
{
  "locale": "zh-CN",
  "language": "Simplified Chinese",
  "version": "1.0.0",
  "errors": {
    "wallet": { ... },
    "miner": { ... },
    "network": { ... },
    "common": { ... }
  },
  "messages": {
    "wallet": { ... },
    "miner": { ... }
  }
}
```

## 使用示例

```python
import json

# 加载翻译
with open('i18n/zh-CN.json', 'r', encoding='utf-8') as f:
    translations = json.load(f)

# 获取错误消息
error_key = "errors.wallet.invalid_amount"
keys = error_key.split('.')
message = translations
for key in keys:
    message = message.get(key, error_key)

# 带参数的消息格式化
def format_message(template: str, **kwargs) -> str:
    return template.format(**kwargs)

# 示例：format_message(translations['errors']['wallet']['dns_resolution_failed'], 
#                      host="rustchain.org", error="超时")
```

## 验证

运行验证脚本确保 JSON 格式正确且包含必需的键：

```bash
python i18n/validate_i18n.py
```

## 添加新语言

1. 复制 `zh-CN.json` 为新文件（如 `ja-JP.json`）
2. 更新 `locale` 字段为新语言代码
3. 翻译所有消息值
4. 运行验证脚本
5. 更新本 README 的语言列表

## 翻译准则

1. **保持一致性**: 相同术语在所有消息中使用相同翻译
2. **保留占位符**: `{variable}` 占位符必须原样保留
3. **简洁明了**: 错误消息应简短且易于理解
4. **技术术语**: 代码、API、URL 等技术内容保持英文

## 贡献

欢迎贡献更多语言翻译！请确保：
- 母语水平翻译
- 覆盖所有错误消息键
- 通过验证脚本

## 许可证

与 RustChain 主项目许可证相同。
