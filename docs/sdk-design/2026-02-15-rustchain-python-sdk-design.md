# RustChain Python SDK 设计文档 (2026-02-15)

## 1. 概述
本项目旨在为 RustChain 区块链开发一个功能完善、易于使用的 Python SDK。该 SDK 将作为开发者与 RustChain 节点交互的主要工具，支持查询链状态、管理账户以及执行加密签名交易。

## 2. 设计原则
- **开发者友好**：提供直观的 API、完整的类型提示和详尽的错误信息。
- **现代化**：基于 Python 3.8+，充分利用类型注解和异步特性。
- **高性能**：采用独立双客户端模式，确保同步和异步场景下的最优表现。
- **类型安全**：使用 Pydantic 进行数据验证和模型化。

## 3. 核心架构

### 3.1 独立双客户端模式
SDK 提供两个主要的客户端类，共享底层的逻辑处理逻辑，但使用不同的网络传输层。
- `RustChainClient`：基于 `httpx` 的同步客户端。
- `AsyncRustChainClient`：基于 `httpx` 的异步客户端。

### 3.2 身份与签名机制 (Identity & Crypto)
将身份认证逻辑与网络通信解耦：
- `Identity` 类：负责持有 Ed25519 私钥/种子，执行签名操作。
- SDK 内部自动处理 Nonce 管理，确保交易的顺序性和防重放保护。

### 3.3 目录结构
```text
rustchain/
├── __init__.py           # 导出常用类
├── client.py             # 同步客户端
├── async_client.py       # 异步客户端
├── identity.py           # 身份与签名逻辑
├── models.py             # Pydantic 数据模型
├── exceptions.py         # 异常定义
└── utils.py              # 通用工具
```

## 4. 关键依赖
- `httpx`：统一的同步/异步 HTTP 请求。
- `pydantic`：数据模型定义与校验。
- `pynacl`：Ed25519 加密签名。

## 5. API 范围
- **Health**: `/health` (节点状态)
- **Chain**: `/api/stats`, `/epoch` (链统计)
- **Miners**: `/api/miners` (矿工列表)
- **Wallet**:
    - `/wallet/balance` (余额查询)
    - `/wallet/transfer/signed` (签名转账)
- **Attestation**: `/attest/submit` (硬件认证)

## 6. 错误处理
定义统一的异常体系，方便用户捕获网络错误、业务逻辑错误（如余额不足）或认证错误（签名无效）。

---
---
