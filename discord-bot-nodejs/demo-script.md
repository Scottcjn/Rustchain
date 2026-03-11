# RustChain Discord Bot 演示脚本

## Bot 信息
- **名称：** bh#6036
- **邀请链接：** https://discord.com/api/oauth2/authorize?client_id=1481195491424211077&permissions=274878024768&scope=bot%20applications.commands

## 命令列表

### 1. `/balance [address]`
**用途：** 查询 RTC 余额
**示例：** `/balance address:0x1234567890abcdef`

### 2. `/miners [limit] [address]`
**用途：** 查看矿工信息
**示例：** 
- `/miners limit:10`（查看前 10 名矿工）
- `/miners address:0x1234...`（查看特定矿工）

### 3. `/epoch [epoch_number]`
**用途：** 查看 epoch 状态
**示例：**
- `/epoch`（当前 epoch）
- `/epoch epoch:12345`（指定 epoch）

### 4. `/health`
**用途：** 检查网络健康状态
**示例：** `/health`

### 5. `/tip @user amount [message]`
**用途：** 打赏其他用户（+5 RTC 奖励）
**示例：** `/tip @friend 5.0 message:Great work!`

## 演示流程

1. **打开 Discord 服务器**
2. **在聊天框输入 `/` 显示命令列表**
3. **依次演示每个命令**
4. **展示命令响应**

## 录制工具

使用 OBS 或 Windows Game Bar (Win+G) 录制

## 提交 PR

1. 上传视频到 GitHub
2. 创建 PR 到 rustchain-bounties
3. 添加 `/claim #1596` 标记
