# RustChain 贡献指南 (CONTRIBUTING_GUIDE.md)

欢迎加入 **RustChain** 开源社区！RustChain 是一个基于 **Proof-of-Antiquity（古董证明）** 共识的 DePIN 网络，致力于让真实物理硬件（尤其是复古计算设备）获得公平的链上奖励。无论你是底层协议开发者、Python/Rust 工程师、复古硬件爱好者，还是技术文档撰写者，你的贡献都将直接推动“物理硅片复兴”运动。

本指南将详细说明如何高效、规范地向本仓库提交代码、修复问题或完善文档。在开始之前，请确保你已阅读 [RustChain 白皮书](docs/RustChain_Whitepaper_Flameholder_v0.97.pdf) 与 [协议规范](PROTOCOL.md)。

---

## 1. 🍴 如何 Fork 与克隆仓库

1. **Fork 仓库**  
   在 GitHub 页面右上角点击 `Fork`，将 `Scottcjn/RustChain` 复制到你的个人账号下。

2. **克隆到本地**  
   ```bash
   git clone git@github.com:<你的用户名>/RustChain.git
   cd RustChain
   ```

3. **配置上游远程仓库**  
   保持与主仓库同步是最佳实践：
   ```bash
   git remote add upstream git@github.com:Scottcjn/RustChain.git
   git fetch upstream
   ```

4. **环境初始化**  
   本项目包含 Python 矿工脚本与可能的 Rust 核心组件。请根据本地环境安装依赖：
   - Python 3.11+（推荐 `pyenv` 或 `conda`）
   - Rust Toolchain（`rustup` + `cargo`）
   - 安装依赖：`pip install -r requirements.txt` 或 `cargo build`

---

## 2. 🌿 分支策略 (Branching Strategy)

RustChain 采用轻量级 **GitFlow + Semantic Versioning** 模型，以保持主分支稳定与迭代高效：

| 分支类型 | 用途 | 示例命名 |
|:---|:---|:---|
| `main` | 生产环境稳定版本，仅接受经测试的 Release | `v1.2.0`, `v1.2.1-hotfix` |
| `develop` | 日常开发集成分支，所有 PR 的目标分支 | - |
| `feature/` | 新功能开发（协议升级、矿工优化、硬件指纹算法） | `feature/simd-fingerprint-v2` |
| `fix/` | Bug 修复（VM 检测误判、Epoch 结算异常等） | `fix/clock-skew-vm-false-positive` |
| `docs/` | 文档、白皮书、Manifesto、教程更新 | `docs/add-mac-g5-setup-guide` |
| `chore/` | 依赖更新、CI/CD 调整、配置修改 | `chore/bump-python-3.12-deps` |

**工作流规范**：
- 始终从最新的 `upstream/develop` 创建分支。
- 优先使用 `git rebase` 同步上游变更，避免产生无意义的 Merge Commit。
- 分支生命周期不超过 14 天，复杂功能请拆分为多个小 PR。

---

## 3. 💻 代码规范 (Code Conventions)

为保证协议安全性与代码可维护性，所有贡献必须通过以下静态检查：

### 🔹 Python 矿工与客户端脚本 (`miners/`, `wallet/`, `scripts/`)
- 格式化：`black --line-length 88`
- 导入排序：`isort --profile black`
- Lint：`ruff check .`
- 类型提示：新增函数必须包含 `typing` 注解，禁止裸 `Any`。

### 🔹 Rust 核心/节点组件 (`src/`, `attestation/`, 若适用)
- 格式化：`cargo fmt --all`
- Lint：`cargo clippy --all-targets -- -D warnings`
- 禁止 `unwrap()`，必须使用 `expect("具体上下文")` 或 `?` 错误传播。

### 🔹 提交信息规范 (Conventional Commits)
```
<type>(<scope>): <subject>

<body (optional)>
```
- `type`: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`
- 示例：`feat(attestation): add thermal-entropy fallback for G4 CPUs`

建议配置 `pre-commit` 钩子自动拦截不规范的提交。

---

## 4. 🔄 PR 提交流程

1. **前置讨论**  
   除拼写错误外，所有功能修改/协议调整请先在 [Issues](https://github.com/Scottcjn/RustChain/issues) 提交 `Feature Request` 或 `Bug Report`，获得 Maintainer 确认后再编码。

2. **创建 PR**  
   - 推送分支至你的 Fork：`git push origin feature/xxx`
   - 在 GitHub 创建 Pull Request，**目标分支设为 `develop`**。
   - 完整填写 PR 模板：
     - 📌 关联 Issue 编号
     - 🔍 变更动机与协议影响（是否影响 RIP-200 共识或 Epoch 结算？）
     - 🧪 测试步骤与日志输出（必须包含硬件/模拟环境验证结果）
     - 📎 截图或时序图（如 Mermaid 流程图）

3. **自动化检查与审查**
   - GitHub Actions 将自动运行 Lint、单元测试与 Docker 构建检查。
   - Maintainer 会在 48 小时内进行 Code Review，可能要求补充测试或重构。
   - 所有评论解决后，PR 将被 **Squash & Merge** 至 `develop`。

---

## 5. 🧪 测试指南 (Testing Guide)

RustChain 的核心挑战在于 **反虚拟化检测** 与 **硬件指纹稳定性**。测试必须覆盖以下维度：

### 🔸 单元测试
- Python 使用 `pytest`，Rust 使用 `cargo test`。
- 所有硬件检查模块必须提供 **Mock 接口**（如模拟 Clock Skew 噪声、平坦化 Cache 曲线），确保 CI 环境无需真实硬件即可通过。
```bash
pytest tests/ -v --cov=miners/ --cov-report=term-missing
```

### 🔸 真实硬件验证 (Bare-Metal)
- 请在物理机（推荐 PowerMac G4/G5、x86 复古主板、ARM SBC）上运行矿工。
- 验证 6 项硬件指纹检查（时钟偏移、缓存延迟、SIMD 特征、热熵、指令抖动、DMI 表）是否返回非 VM 特征。
- **注意**：Docker 容器默认触发 VM 检测降权机制（见 `Dockerfile.miner` 注释），真实奖励测试必须在裸机执行。

### 🔸 集成与 Epoch 测试
- 启动本地测试网节点：`python miners/testnet_setup.py`
- 模拟 144 Slot 完整 Epoch 生命周期，验证结算哈希锚定到 Ergo 的接口兼容性。
- 检查 RTC 分配逻辑是否符合 `1 CPU = 1 Vote` 加权模型。

---

## 6. 📖 文档贡献规范

文档是协议透明度的基石。RustChain 文档位于 `docs/` 目录，贡献需遵循：

- **结构规范**：使用标准 Markdown，标题层级不超过 4 级，代码块标明语言。
- **技术准确性**：引用协议参数（如 Epoch 长度、RIP-200 版本、Multiplier 算法）必须与 `PROTOCOL.md` 或最新版白皮书一致。
- **Markdown Lint**：提交前运行 `markdownlint *.md` 修复格式警告。
- **翻译与本地化**：新增非英文文档请存放于 `docs/i18n/<lang>/`，并同步更新主文档目录索引。
- **教程类文档**：必须包含前置依赖、分步命令、预期输出、故障排查（Troubleshooting）章节。

---

## 7. 📜 行为准则 (Code of Conduct)

RustChain 社区遵循 **贡献者公约 (Contributor Covenant v2.1)**，并结合项目特性补充以下原则：

1. **尊重硬件历史**：我们致力于保护与验证真实物理计算设备。禁止发布嘲讽复古硬件、贬低开源协作的言论。
2. **反对作弊与滥用**：严禁利用云 VM、容器集群、硬件模拟器进行“挖矿刷奖”或伪造指纹数据。此类行为一经发现将永久封禁节点地址与仓库权限。
3. **建设性反馈**：在 Issue 与 PR Review 中保持专业、具体、可执行。对事不对人，鼓励 Pair Debugging 与知识共享。
4. **隐私与合规**：硬件指纹仅用于共识验证，不得收集或泄露用户隐私数据。所有数据流转需符合开源隐私设计原则。
5. **举报机制**：若发现违反准则的行为，请发送邮件至 `conduct@rustchain.org` 或通过 GitHub 安全表单提交。核心团队将严格保密并公正处理。

---

## 🌟 致谢与后续

每一行代码、每一次测试、每一页文档的完善，都在让“老旧硅片”在去中心化网络中重焕生机。RustChain 不属于任何单一组织，它属于所有相信 **物理实体价值** 与 **开放协作** 的构建者。

感谢你的贡献。愿复古硬件的时钟偏移，永远比虚拟机的完美正弦波更动听。

🔗 **相关链接**  
[Explorer](https://rustchain.org/explorer/) · [Whitepaper](docs/RustChain_Whitepaper_Flameholder_v0.97.pdf) · [Discord Community](https://discord.gg/rustchain) · [License](LICENSE)

> *“And all hardware becomes old. It's just a matter of time.”*