# RustChain Telegram Bot 部署指南

## 目录

1. [快速部署](#快速部署)
2. [Node.js 版本部署](#nodejs-版本部署)
3. [Python 版本部署](#python-版本部署)
4. [Docker 部署](#docker-部署)
5. [服务器部署](#服务器部署)
6. [故障排查](#故障排查)

---

## 快速部署

### 步骤 1: 创建 Telegram Bot

1. 打开 Telegram，搜索 `@BotFather`
2. 发送 `/newbot` 命令
3. 按提示输入：
   - 机器人名称（如：RustChain Bot）
   - 机器人用户名（如：rustchain_notification_bot）
4. 保存返回的 API Token

### 步骤 2: 获取聊天 ID

1. 在 Telegram 中启动刚创建的机器人
2. 发送 `/start` 命令
3. 访问：`https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. 在返回的 JSON 中找到 `"chat":{"id":123456789}`

### 步骤 3: 配置环境变量

```bash
# Node.js
cp .env.example .env
# 编辑 .env 文件

# Python
cd python
cp .env.example .env
# 编辑 .env 文件
```

### 步骤 4: 启动机器人

```bash
# Node.js
npm install
npm start

# Python
pip install -r requirements.txt
python bot.py
```

---

## Node.js 版本部署

### 本地开发

```bash
# 1. 安装 Node.js (v18+)
# 下载地址：https://nodejs.org/

# 2. 克隆项目
cd rustchain-telegram-bot

# 3. 安装依赖
npm install

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入：
# - TELEGRAM_BOT_TOKEN=你的机器人 token
# - ALLOWED_CHAT_IDS=你的聊天 ID

# 5. 启动
npm start

# 开发模式（自动重启）
npm run dev
```

### 生产环境（PM2）

```bash
# 1. 安装 PM2
npm install -g pm2

# 2. 进入项目目录
cd rustchain-telegram-bot

# 3. 安装依赖
npm install --production

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 5. 启动应用
pm2 start ecosystem.config.js

# 6. 查看日志
pm2 logs rustchain-bot

# 7. 设置开机自启
pm2 startup
# 复制输出的命令并执行
pm2 save
```

### PM2 常用命令

```bash
pm2 status          # 查看状态
pm2 stop rustchain-bot    # 停止
pm2 restart rustchain-bot # 重启
pm2 delete rustchain-bot  # 删除
pm2 logs rustchain-bot    # 查看日志
```

---

## Python 版本部署

### 本地开发

```bash
# 1. 安装 Python (v3.8+)
# 下载地址：https://www.python.org/

# 2. 进入项目目录
cd rustchain-telegram-bot/python

# 3. 创建虚拟环境（推荐）
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 6. 启动
python bot.py
```

### 生产环境（Systemd）

```bash
# 1. 创建服务文件
sudo nano /etc/systemd/system/rustchain-bot.service
```

添加以下内容：

```ini
[Unit]
Description=RustChain Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/rustchain-telegram-bot/python
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 2. 启动服务
sudo systemctl daemon-reload
sudo systemctl enable rustchain-bot
sudo systemctl start rustchain-bot

# 3. 查看状态
sudo systemctl status rustchain-bot

# 4. 查看日志
sudo journalctl -u rustchain-bot -f
```

---

## Docker 部署

### 构建和运行

```bash
# 1. 进入项目目录
cd rustchain-telegram-bot

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 3. 构建镜像
docker build -t rustchain-telegram-bot .

# 4. 运行容器
docker run -d \
  --name rustchain-bot \
  --restart unless-stopped \
  --env-file .env \
  rustchain-telegram-bot

# 5. 查看日志
docker logs -f rustchain-bot

# 6. 停止容器
docker stop rustchain-bot

# 7. 删除容器
docker rm rustchain-bot
```

### Docker Compose

创建 `docker-compose.yml`:

```yaml
version: '3.8'

services:
  rustchain-bot:
    build: .
    container_name: rustchain-bot
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
```

运行：

```bash
docker-compose up -d
docker-compose logs -f
```

---

## 服务器部署

### VPS 部署（Ubuntu 20.04+）

```bash
# 1. 更新系统
sudo apt update && sudo apt upgrade -y

# 2. 安装 Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 3. 安装 Git
sudo apt install -y git

# 4. 克隆项目
git clone <your-repo-url>
cd rustchain-telegram-bot

# 5. 安装依赖
npm install

# 6. 安装 PM2
sudo npm install -g pm2

# 7. 配置环境变量
cp .env.example .env
nano .env
# 编辑配置

# 8. 启动服务
pm2 start ecosystem.config.js
pm2 startup
pm2 save

# 9. 配置防火墙（如需要）
sudo ufw allow 3000/tcp
sudo ufw enable
```

### 云服务器（阿里云/腾讯云）

1. 购买云服务器（最低配置：1 核 1G）
2. 按照 VPS 部署步骤操作
3. 配置安全组规则
4. 建议使用 HTTPS 的 RPC 节点

---

## 故障排查

### 常见问题

#### 1. 机器人无响应

```bash
# 检查 Token 是否正确
# 检查网络连通性
ping api.telegram.org

# 查看日志
pm2 logs rustchain-bot
# 或
docker logs rustchain-bot
```

#### 2. 余额查询失败

```bash
# 检查 RPC 节点是否可用
curl -X POST https://rpc.rustchain.io \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# 检查钱包地址格式
# RustChain 地址应以 RTC 开头
```

#### 3. 交易通知不推送

```bash
# 检查 ALLOWED_CHAT_IDS 配置
# 确认聊天 ID 格式正确
# 查看日志确认交易监控是否运行
```

#### 4. 内存占用过高

```bash
# Node.js 版本
# 在 ecosystem.config.js 中设置 max_memory_restart

# Python 版本
# 定期重启服务
sudo systemctl restart rustchain-bot
```

### 日志位置

```bash
# PM2
pm2 logs rustchain-bot

# Systemd
sudo journalctl -u rustchain-bot -f

# Docker
docker logs -f rustchain-bot

# 文件日志
./logs/error.log
./logs/output.log
```

### 性能优化

1. **调整检查间隔**
   - 默认 30 秒
   - 可降低到 60 秒减少资源占用

2. **限制交易记录**
   - 默认保留最近 100 条
   - 可根据需要调整

3. **使用专用 RPC 节点**
   - 避免使用公共节点
   - 考虑搭建私有节点

---

## 安全建议

1. **保护 Token**
   - 不要将 `.env` 文件提交到 Git
   - 使用环境变量管理工具

2. **限制访问**
   - 配置 `ALLOWED_CHAT_IDS`
   - 定期审查授权列表

3. **监控日志**
   - 设置日志告警
   - 定期检查异常

4. **备份配置**
   - 定期备份 `.env` 文件
   - 记录重要配置变更

---

## 技术支持

如遇到问题：

1. 查看日志文件
2. 检查配置文件
3. 确认网络连接
4. 查阅文档

---

最后更新：2026-03-13
