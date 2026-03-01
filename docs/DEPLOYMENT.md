# 部署指南

本文档详细说明如何部署 OpenClaw Mobile。

## 前置条件

- OpenClaw Gateway 已安装并运行
- Python 3.7+ (用于运行 server.py)
- 现代浏览器 (Chrome, Firefox, Safari, Edge)

## 部署方式

### 方式一：直接部署（推荐）

适合内网使用、Tailscale 网络环境。

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/openclaw-mobile.git
cd openclaw-mobile

# 2. 配置 server.py
vim server.py
# 修改以下配置：
# - BIND_HOST: 监听地址（推荐内网 IP）
# - PORT: 监听端口（默认 8080）
# - GATEWAY_HTTP: Gateway 地址（默认 http://127.0.0.1:18789）

# 3. 启动服务
python3 server.py
```

### 方式二：Systemd 服务（生产环境）

适合长期运行的服务。

```bash
# 1. 创建服务文件
cat > ~/.config/systemd/user/openclaw-web.service << EOF
[Unit]
Description=OpenClaw Web Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /path/to/openclaw-mobile/server.py
Restart=on-failure
RestartSec=5
WorkingDirectory=/path/to/openclaw-mobile

[Install]
WantedBy=default.target
EOF

# 2. 启用并启动服务
systemctl --user daemon-reload
systemctl --user enable openclaw-web
systemctl --user start openclaw-web

# 3. 查看状态
systemctl --user status openclaw-web
```

### 方式三：Docker（可选）

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

EXPOSE 8080

CMD ["python3", "server.py"]
```

```bash
# 构建镜像
docker build -t openclaw-mobile .

# 运行容器
docker run -d \
  --name openclaw-mobile \
  -p 8080:8080 \
  --network host \
  openclaw-mobile
```

## 配置 Gateway

### 1. 获取 Token

```bash
# 从 Gateway 配置获取
cat ~/.openclaw/openclaw.json | jq -r '.gateway.auth.token'

# 或查看 Gateway 启动日志
```

### 2. 配置 allowedOrigins

编辑 `~/.openclaw/openclaw.json`：

```json
{
  "gateway": {
    "controlUi": {
      "allowedOrigins": [
        "http://localhost:8080",
        "http://localhost:18789",
        "http://your-internal-ip:8080",
        "http://your-host.tailXXXX.ts.net:8080",
        "https://your-domain.com"
      ]
    }
  }
}
```

### 3. 重启 Gateway

```bash
# 使用 systemctl
systemctl --user restart openclaw-gateway

# 或使用 openclaw 命令
openclaw gateway restart
```

## 访问方式

### 本地访问

```
http://localhost:8080/mobile.html
```

### 内网访问

```
http://<内网IP>:8080/mobile.html
```

### Tailscale 访问

```
http://<hostname>.tailXXXX.ts.net:8080/mobile.html
```

### 云端口转发访问

如果使用云服务商的端口转发：

1. HTTP 转发 → 8080 端口
2. WSS 转发 → 18789 端口
3. 配置域名映射（见 [CONFIGURATION.md](CONFIGURATION.md)）

## 故障排除

### WebSocket 连接失败

**错误**：`WebSocket closed: 1008 origin not allowed`

**解决**：在 Gateway 的 `allowedOrigins` 中添加访问域名。

### Mixed Content 错误

**错误**：浏览器阻止 HTTPS 页面访问 WS 连接

**解决**：使用 WSS（WebSocket Secure）协议。

### Token 无效

**错误**：认证失败

**解决**：检查 Token 是否正确，是否过期。

## 安全建议

1. **不要暴露到公网**
   - 使用内网 IP
   - 使用 Tailscale VPN
   - 配置防火墙规则

2. **定期更换 Token**
   ```bash
   # 生成新 Token
   openssl rand -base64 32

   # 更新 Gateway 配置
   vim ~/.openclaw/openclaw.json
   ```

3. **使用 HTTPS**
   - 配置反向代理（Nginx, Caddy）
   - 使用 Let's Encrypt 证书

4. **限制访问来源**
   - 配置 `allowedOrigins` 白名单
   - 使用防火墙限制 IP
