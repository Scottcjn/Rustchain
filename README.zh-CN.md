# RustChain

一个用 Rust 构建的轻量级区块链实现，结合 Python 的区块链浏览器和网络 API。

## 概述

RustChain 是一个完整的区块链系统，包含以下组件：
- **Rust 区块链核心**：高性能的区块链引擎
- **Python 网络节点**：处理网络通信和 API
- **区块链浏览器**：用于探索区块和交易的 Web 界面
- **原生代币 (RTC)**：系统的内置货币

## 功能特性

### 区块链核心
- ✅ **工作量证明 (PoW)**：安全的共识机制
- ✅ **动态难度调整**：根据网络算力自动调节
- ✅ **UTXO 模型**：未花费交易输出追踪
- ✅ **交易验证**：完整的签名验证和余额检查
- ✅ **内存池**：待处理交易管理
- ✅ **区块验证**：完整的区块和链验证

### 网络层
- 🌐 **点对点网络**：去中心化节点通信
- 🔄 **节点发现**：自动发现和连接对等节点
- 📡 **区块同步**：与网络同步区块链状态
- 💾 **持久化存储**：SQLite 数据库存储

### API 和用户界面
- 🖥️ **RESTful API**：完整的区块链 API 端点
- 🌐 **Web 界面**：用户友好的区块链浏览器
- 💰 **钱包功能**：查看余额和创建交易
- 📊 **网络统计**：实时网络健康监控

## 快速开始

### 前提条件

```bash
# Rust (1.70+)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Python (3.8+)
python3 --version

# Git
git --version
```

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
```

2. **构建 Rust 组件**
```bash
cd rustchain
cargo build --release
cd ..
```

3. **安装 Python 依赖**
```bash
pip install -r requirements.txt
```

4. **启动区块链节点**
```bash
# 启动主节点
python node/rustchain_v2_integrated_v2.2.1_rip200.py

# 或使用新的节点实现
python node_manager.py
```

5. **访问区块链浏览器**
```
打开浏览器访问: http://localhost:5000
```

## 项目结构

```
Rustchain/
├── rustchain/           # Rust 区块链核心
│   ├── src/
│   │   ├── blockchain.rs    # 区块链逻辑
│   │   ├── block.rs        # 区块结构
│   │   ├── transaction.rs  # 交易处理
│   │   └── main.rs         # 入口点
│   └── Cargo.toml
├── node/               # Python 网络节点
│   └── rustchain_v2_integrated_v2.2.1_rip200.py
├── static/             # Web 资源
├── templates/          # HTML 模板
├── *.py               # Python 组件
└── README.md
```

## API 端点

### 区块链信息
- `GET /` - 区块链浏览器主页
- `GET /api/blockchain` - 完整区块链数据
- `GET /api/latest_block` - 最新区块信息
- `GET /api/blockchain_info` - 区块链统计信息

### 区块操作
- `GET /api/block/<int:index>` - 按索引获取区块
- `GET /api/block_by_hash/<hash>` - 按哈希获取区块
- `POST /api/mine` - 挖掘新区块

### 交易
- `GET /api/transaction/<tx_hash>` - 获取交易详情
- `POST /api/transaction` - 创建新交易
- `GET /api/mempool` - 查看内存池

### 钱包
- `GET /api/balance/<address>` - 查询地址余额
- `POST /api/wallet/generate` - 生成新钱包地址

### 网络
- `GET /api/peers` - 查看连接的节点
- `GET /api/network_stats` - 网络统计信息

## 挖矿

RustChain 使用工作量证明共识机制。要开始挖矿：

```bash
# 通过 API 挖矿
curl -X POST http://localhost:5000/api/mine

# 或使用 Web 界面
# 访问 http://localhost:5000 并点击"挖掘区块"
```

## 配置

主要配置选项在 `node/rustchain_v2_integrated_v2.2.1_rip200.py` 中：

```python
# 网络配置
DEFAULT_PORT = 5000
BLOCKCHAIN_PORT = 8333

# 挖矿配置
MINING_REWARD = 10.0
DIFFICULTY_TARGET = "0000"

# 数据库配置
DB_PATH = "rustchain.db"
```

## 开发

### 运行测试

```bash
# Rust 测试
cd rustchain
cargo test

# Python 测试
python -m pytest tests/
```

### 代码格式化

```bash
# Rust 格式化
cd rustchain
cargo fmt

# Python 格式化
black *.py node/*.py
ruff check *.py node/*.py
```

## 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m '添加某个功能'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

### 代码规范

- **Rust**：遵循 `rustfmt` 标准
- **Python**：遵循 PEP 8，使用 `black` 格式化
- **提交信息**：使用清晰的描述性信息
- **测试**：为新功能添加测试

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 路线图

### 版本 3.0 (规划中)
- [ ] 智能合约支持
- [ ] 权益证明 (PoS) 共识
- [ ] 分片技术
- [ ] 跨链兼容性

### 版本 2.3 (开发中)
- [ ] 改进的网络协议
- [ ] GraphQL API
- [ ] 移动端钱包
- [ ] 性能优化

## 社区

- **GitHub Issues**：报告问题和请求功能
- **Discussions**：技术讨论和问题解答
- **Discord**：实时社区聊天 [即将推出]

## 致谢

感谢所有为 RustChain 做出贡献的开发者和社区成员。

---

**免责声明**：RustChain 是一个教育性项目。请不要在生产环境中使用，除非你完全理解相关风险。
