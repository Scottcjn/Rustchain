# RustChain Python SDK 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个支持同步和异步双接口的 RustChain Python SDK，具备加密签名交易和硬件认证功能。

**Architecture:** 采用独立双客户端模式（`RustChainClient` 和 `AsyncRustChainClient`）。身份认证（Ed25519 签名）与网络请求解耦，使用 Pydantic 进行数据模型化。

**Tech Stack:** Python 3.8+, `httpx`, `pydantic`, `PyNaCl`.

---

### Task 1: 项目初始化与依赖配置

**Files:**
- Create: `pyproject.toml`
- Create: `src/rustchain/__init__.py`

**Step 1: 创建 pyproject.toml 并配置依赖**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "rustchain-sdk"
version = "0.1.0"
description = "Python SDK for RustChain Blockchain"
requires-python = ">=3.8"
dependencies = [
    "httpx>=0.24.0",
    "pydantic>=2.0.0",
    "pynacl>=1.5.0",
]

[project.optional-dependencies]
test = ["pytest", "pytest-asyncio", "respx"]

[tool.hatch.build.targets.wheel]
packages = ["src/rustchain"]
```

**Step 2: 安装依赖**

运行: `pip install -e ".[test]"`
预期: 成功安装 `httpx`, `pydantic`, `pynacl` 等。

**Step 3: 提交**

```bash
git add pyproject.toml src/rustchain/__init__.py
git commit -m "chore: initialize project and dependencies"
```

---

### Task 2: 定义数据模型 (Models)

**Files:**
- Create: `src/rustchain/models.py`
- Create: `tests/test_models.py`

**Step 1: 编写数据模型测试**

```python
from rustchain.models import Miner
def test_miner_model():
    data = {"miner": "abc", "hardware_type": "x86", "antiquity_multiplier": 0.8, "last_attest": 123}
    miner = Miner(**data)
    assert miner.miner == "abc"
```

**Step 2: 运行测试并验证失败**

运行: `pytest tests/test_models.py`
预期: FAIL (ModuleNotFoundError)

**Step 3: 实现 Pydantic 模型**

```python
from pydantic import BaseModel
from typing import List, Optional

class Miner(BaseModel):
    miner: str
    hardware_type: str
    antiquity_multiplier: float
    last_attest: int

class Stats(BaseModel):
    epoch: int
    total_miners: int
    total_balance: float
```

**Step 4: 运行测试并验证通过**

运行: `pytest tests/test_models.py`
预期: PASS

**Step 5: 提交**

```bash
git add src/rustchain/models.py tests/test_models.py
git commit -m "feat: add data models using pydantic"
```

---

### Task 3: 实现身份认证与签名逻辑 (Identity)

**Files:**
- Create: `src/rustchain/identity.py`
- Create: `tests/test_identity.py`

**Step 1: 编写签名逻辑测试**

```python
from rustchain.identity import Identity
def test_identity_signing():
    id = Identity.from_seed("test" * 8)
    msg = b"hello"
    sig = id.sign(msg)
    assert len(sig) == 64
```

**Step 2: 运行测试并验证失败**

运行: `pytest tests/test_identity.py`
预期: FAIL

**Step 3: 使用 PyNaCl 实现签名逻辑**

```python
import nacl.signing
import nacl.encoding

class Identity:
    def __init__(self, signing_key: nacl.signing.SigningKey):
        self._key = signing_key
        self.address = self._key.verify_key.encode(nacl.encoding.HexEncoder).decode()

    @classmethod
    def from_seed(cls, seed_hex: str):
        return cls(nacl.signing.SigningKey(seed_hex, encoder=nacl.encoding.HexEncoder))

    def sign(self, message: bytes) -> str:
        return self._key.sign(message).signature.hex()
```

**Step 4: 运行测试并验证通过**

运行: `pytest tests/test_identity.py`
预期: PASS

**Step 5: 提交**

```bash
git commit -m "feat: implement ed25519 identity and signing"
```

---

### Task 4: 实现同步客户端 (RustChainClient)

**Files:**
- Create: `src/rustchain/client.py`
- Create: `tests/test_client_sync.py`

**Step 1: 编写同步请求测试 (使用 respx 模拟)**

**Step 2: 实现基于 httpx.Client 的 RustChainClient**

**Step 3: 运行测试并验证通过**

**Step 4: 提交**

---

### Task 5: 实现异步客户端 (AsyncRustChainClient)

**Files:**
- Create: `src/rustchain/async_client.py`
- Create: `tests/test_client_async.py`

**Step 1: 编写异步请求测试**

**Step 2: 实现基于 httpx.AsyncClient 的客户端**

**Step 3: 运行测试并验证通过**

**Step 4: 提交**

---

### Task 6: 集成转账与 Nonce 管理

**Files:**
- Modify: `src/rustchain/client.py`
- Modify: `src/rustchain/async_client.py`

**Step 1: 在客户端中添加自动 Nonce 获取逻辑**
**Step 2: 实现 signed_transfer 方法**
**Step 3: 编写集成测试**
**Step 4: 提交**
