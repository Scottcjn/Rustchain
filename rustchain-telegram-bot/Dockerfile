FROM node:18-alpine

WORKDIR /app

# 复制 package 文件
COPY package*.json ./

# 安装依赖
RUN npm ci --only=production

# 复制应用代码
COPY index.js ./
COPY .env.example ./.env.example

# 创建非 root 用户
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

USER nodejs

# 暴露端口（如果需要 webhook）
EXPOSE 3000

# 启动命令
CMD ["node", "index.js"]
