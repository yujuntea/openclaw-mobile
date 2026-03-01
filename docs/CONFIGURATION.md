# 配置说明

本文档说明 OpenClaw Mobile 的各项配置。

## server.py 配置

### 基本配置

```python
# 端口配置
PORT = 8080  # Web 服务端口

# Gateway 地址
GATEWAY_HTTP = "http://127.0.0.1:18789"  # Gateway HTTP 地址

# 目录配置
INBOUND_DIR = "/root/.openclaw/media/inbound"  # 入站文件目录
WORKSPACE_DIR = "/root/.openclaw/workspace"     # 工作目录
MEDIA_DIR = "/root/.openclaw/media"             # 媒体目录
DASHBOARD_DIR = "/path/to/openclaw/dist/control-ui"  # Dashboard 目录

# 监听配置
BIND_HOST = "0.0.0.0"  # 监听地址
# 推荐配置：
# - 内网 IP: "192.168.1.100"
# - Tailscale IP: "100.x.x.x"
# - 本地开发: "127.0.0.1"
```

### 绑定地址选择

| BIND_HOST | 说明 | 安全性 |
|-----------|------|--------|
| `127.0.0.1` | 仅本地访问 | ⭐⭐⭐⭐⭐ 最安全 |
| `192.168.x.x` | 内网访问 | ⭐⭐⭐⭐ 推荐 |
| `100.x.x.x` | Tailscale 内网 | ⭐⭐⭐⭐ 推荐 |
| `0.0.0.0` | 所有接口 | ⭐⭐ 需配置防火墙 |

## mobile.html 配置

### 登录状态持久化

```javascript
// 登录状态有效期（毫秒）
const LOGIN_EXPIRY_MS = 60 * 60 * 1000;  // 默认 1 小时

// 修改为其他值：
const LOGIN_EXPIRY_MS = 30 * 60 * 1000;  // 30 分钟
const LOGIN_EXPIRY_MS = 2 * 60 * 60 * 1000;  // 2 小时
const LOGIN_EXPIRY_MS = 24 * 60 * 60 * 1000;  // 24 小时
```

### 历史消息存储

```javascript
// 历史消息最大数量
const MAX_HISTORY = 100;  // 默认 100 条

// 修改为其他值：
const MAX_HISTORY = 50;   // 50 条
const MAX_HISTORY = 200;  // 200 条
const MAX_HISTORY = 500;  // 500 条
```

### 腾讯云端口转发映射

```javascript
// 腾讯云端口转发域名映射
const TENCENT_WSS_MAPPING = {
  // HTTP 域名 → WSS 域名
  'your-http-prefix.orcaterm.cloud.tencent.com': 
  'your-wss-prefix.orcaterm.cloud.tencent.com',
  
  // 可以添加多个映射
  // 'another-http.example.com': 'another-wss.example.com',
};
```

### WebSocket 地址智能检测

mobile.html 会自动检测访问环境并选择正确的 WebSocket 地址：

```javascript
// 检测逻辑：
if (hostname.includes('.orcaterm.cloud.tencent.com')) {
  // 腾讯云：使用 WSS 协议和映射域名
  wsUrl = 'wss://' + TENCENT_WSS_MAPPING[hostname] + '/';
} else if (hostname.includes('.tailXXXX.ts.net')) {
  // Tailscale：使用 WS 协议和 18789 端口
  wsUrl = 'ws://' + hostname + ':18789/';
} else {
  // 其他：使用默认地址
  wsUrl = 'ws://localhost:18789/';
}
```

## Gateway 配置

### openclaw.json 示例

```json
{
  "gateway": {
    "port": 18789,
    "mode": "local",
    "bind": "tailnet",
    "controlUi": {
      "allowedOrigins": [
        "http://127.0.0.1:18789",
        "http://localhost:18789",
        "http://localhost:8080",
        "http://your-host.tailXXXX.ts.net:8080",
        "https://your-domain.com"
      ],
      "allowInsecureAuth": true,
      "dangerouslyDisableDeviceAuth": false
    },
    "auth": {
      "mode": "token",
      "token": "YOUR_SECRET_TOKEN_HERE"
    }
  }
}
```

### bind 配置选项

| bind | 说明 |
|------|------|
| `loopback` | 仅本地访问 |
| `tailnet` | Tailscale 内网 |
| IP 地址 | 指定 IP |

### allowedOrigins 配置

```json
{
  "allowedOrigins": [
    "http://localhost:8080",           // 本地开发
    "http://localhost:18789",          // Dashboard
    "http://192.168.1.100:8080",       // 内网访问
    "http://host.tailXXXX.ts.net:8080", // Tailscale
    "https://your-domain.com",         // HTTPS 域名
    "https://forward-xxx.example.com"  // 端口转发
  ]
}
```

## 云端口转发配置

### 腾讯云端口转发

1. 创建两个转发规则：

| 规则类型 | 域名前缀 | 目标端口 | 用途 |
|----------|----------|----------|------|
| HTTP/HTTPS | `forward-http-` | 8080 | Mobile 页面、文件浏览 |
| WebSocket | `forward-wss-` | 18789 | Gateway WebSocket |

2. 配置域名映射：

```javascript
const TENCENT_WSS_MAPPING = {
  'forward-http-xxx.orcaterm.cloud.tencent.com': 
  'forward-wss-xxx.orcaterm.cloud.tencent.com'
};
```

3. 添加到 Gateway allowedOrigins：

```json
{
  "allowedOrigins": [
    "https://forward-http-xxx.orcaterm.cloud.tencent.com",
    "https://forward-wss-xxx.orcaterm.cloud.tencent.com"
  ]
}
```

## 反向代理配置

### Nginx

```nginx
# HTTP 代理 (8080)
server {
    listen 8080;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# WebSocket 代理 (18789)
server {
    listen 18789;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:18789;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Caddy (自动 HTTPS)

```
# Caddyfile
your-domain.com:8080 {
    reverse_proxy localhost:8080
}

ws.your-domain.com {
    reverse_proxy localhost:18789
}
```

## 环境变量

可以通过环境变量配置：

```bash
# Gateway Token
export OPENCLAW_TOKEN="your-token-here"

# Gateway URL
export OPENCLAW_GATEWAY="ws://localhost:18789"

# Web Server Port
export OPENCLAW_WEB_PORT="8080"
```
