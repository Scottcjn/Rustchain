# Sprint Node Operator Guide：修复仓库克隆URL

## 概述

本文档针对Sprint节点运营商在安装过程中遇到的仓库克隆URL错误问题，提供了明确的修正方案。当前指南中的安装步骤错误地指示运营商克隆`rustchain-bounties`仓库，而正确操作应为克隆主Rustchain仓库。本文档将详细说明修正内容、原因及验证步骤。

## 问题描述

在当前的`node-operator-guide.md`文档中，**安装（Install）** 部分包含以下错误指令：

```bash
git clone https://github.com/Scottcjn/rustchain-bounties.git
```

该指令克隆的是`rustchain-bounties`仓库，该仓库是一个辅助性仓库，主要用于管理赏金任务和贡献者激励。而Sprint节点运行所需的核心代码和配置位于主**Rustchain**仓库中。

## 修正内容

### 原指令（错误）

```bash
# 克隆辅助仓库（不推荐用于节点运行）
git clone https://github.com/Scottcjn/rustchain-bounties.git
```

### 修正后指令（正确）

```bash
# 克隆主Rustchain仓库（用于Sprint节点设置）
git clone https://github.com/Scottcjn/rustchain.git
```

## 修正原因

| 项目 | 原仓库 (rustchain-bounties) | 正确仓库 (rustchain) |
|------|-----------------------------|----------------------|
| **用途** | 赏金任务管理、贡献者激励 | 主链节点运行、核心协议实现 |
| **包含文件** | 任务说明、奖励规则、贡献指南 | 节点二进制文件、配置文件、启动脚本 |
| **更新频率** | 不定期更新，与主链版本可能不同步 | 与Sprint节点版本同步更新 |
| **依赖关系** | 依赖于主仓库的某些输出 | 独立运行，包含所有节点依赖 |

使用错误仓库将导致以下问题：
- 缺少节点运行必需的二进制文件（如`rustchain-node`）
- 无法找到正确的配置文件（`config.toml`、`genesis.json`等）
- 与Sprint网络版本不兼容，导致连接失败

## 验证步骤

修正后，请按以下步骤验证克隆操作是否正确：

1. **执行克隆命令**
   ```bash
   git clone https://github.com/Scottcjn/rustchain.git
   cd rustchain
   ```

2. **检查仓库内容**
   ```bash
   ls -la
   # 应看到以下关键文件和目录：
   # - Cargo.toml（Rust项目配置文件）
   # - node/（节点主目录）
   # - config/（配置模板）
   # - scripts/（启动脚本）
   ```

3. **验证节点版本**
   ```bash
   cat Cargo.toml | grep "version"
   # 输出应显示与Sprint网络兼容的版本号
   ```

4. **确认与Sprint网络同步**
   ```bash
   git branch -a
   # 应包含与Sprint网络对应的分支（如：sprint-v1.0）
   ```

## 总结

本次修正将`node-operator-guide.md`中的克隆URL从`rustchain-bounties`仓库更新为正确的`rustchain`主仓库。所有Sprint节点运营商应：

- **立即更新**本地文档中的克隆指令
- **重新克隆**正确仓库（如已克隆错误仓库）
- **验证**仓库内容与Sprint网络版本一致

**重要提醒**：使用错误仓库可能导致节点无法启动或网络连接失败。请务必在克隆后执行上述验证步骤，确保环境配置正确。

---

*文档版本：v2.0*  
*最后更新：2024年*  
*适用对象：Sprint节点运营商*