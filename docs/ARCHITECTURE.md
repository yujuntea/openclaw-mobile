# 技术架构

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        openclaw-mobile                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     WebSocket      ┌──────────────────┐      │
│  │              │ ◄─────────────────► │                  │      │
│  │  mobile.html │                    │  OpenClaw Gateway │      │
│  │  (前端)      │     HTTP/WS        │  (WebSocket 服务) │      │
│  │              │ ◄─────────────────► │                  │      │
│  └──────┬───────┘                    └──────────────────┘      │
│         │                                                       │
│         │ HTTP (图片上传)                                        │
│         ▼                                                       │
│  ┌──────────────┐     HTTP 代理     ┌──────────────────┐       │
│  │              │ ─────────────────► │                  │       │
│  │  server.py   │                    │  OpenClaw Gateway │       │
│  │  (后端)      │ ◄───────────────── │  (HTTP API)      │       │
│  │              │    静态文件服务     │                  │       │
│  └──────────────┘                    └──────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 技术栈

### 前端 (mobile.html)

| 技术 | 用途 |
|------|------|
| 原生 JavaScript | 无框架依赖，轻量高效 |
| WebSocket API | 实时双向通信 |
| CSS3 | 现代 UI 设计，深色主题 |
| LocalStorage | 登录状态持久化 |

### 后端 (server.py)

| 技术 | 用途 |
|------|------|
| Python http.server | 轻量级 HTTP 服务器 |
| urllib.request | HTTP 代理转发 |
| base64 | 图片编码处理 |

## 核心模块

### 1. WebSocket 客户端 (GwClient)

**职责**：管理与 Gateway 的 WebSocket 连接

```javascript
class GwClient {
  constructor(url, token, sessionKey, onEvent, onConnect, onDisconnect) {
    this.url = url;           // WebSocket 地址
    this.token = token;       // 认证 Token
    this.sessionKey = sessionKey; // 会话 ID
    this.onEvent = onEvent;   // 事件回调
  }
  
  // 核心方法
  connect()           // 建立 WebSocket 连接
  sendConnect()       // 发送认证消息
  request(method, params)  // 发送请求
  sendMessage(message)     // 发送聊天消息
  getHistory(limit)        // 获取历史消息
}
```

**连接流程**：
```
1. 建立 WebSocket 连接
   ↓
2. 收到 connect.challenge（可选）
   ↓
3. 发送 { method: "connect", auth: { token: "xxx" } }
   ↓
4. 收到 hello-ok 或 hello 事件
   ↓
5. 认证成功，开始通信
```

### 2. 消息处理器 (handleMessage)

**支持的消息类型**：

| 类型 | 说明 | 处理方式 |
|------|------|----------|
| `res` | 请求响应 | 匹配 pending 请求，resolve/reject |
| `event` | 事件通知 | 调用 onEvent 回调 |
| `connect.challenge` | 认证挑战 | 保存 nonce，发送认证 |
| `hello` | 连接成功 | 标记 authenticated |
| `chat.message` | 聊天消息 | 渲染消息气泡 |

### 3. 流式输出渲染

**实现原理**：
- Gateway 通过 `event` 事件推送增量内容
- 前端实时更新 DOM，实现打字机效果
- 支持文本、思考过程、工具调用的流式渲染

**消息结构**：
```javascript
{
  type: 'event',
  event: 'chat.message',
  payload: {
    content: [
      { type: 'text', text: '...' },
      { type: 'thinking', thinking: '...' },
      { type: 'tool_call', name: '...', input: {...} },
      { type: 'tool_result', result: '...' }
    ]
  }
}
```

### 4. 思考过程显示

**CSS 样式**：
```css
.thinking {
  background: linear-gradient(135deg, #1a1a2e, #16213e);
  border-left: 4px solid var(--purple);
  /* 紫色渐变背景 + 左边框 */
}
```

**渲染逻辑**：
```javascript
// 检测思考内容
const thinkingContent = message?.thinking || 
                       message?.message?.thinking ||
                       message?.content?.find(c => c.thinking)?.thinking;

// 渲染思考区块
if (thinkingContent) {
  renderThinking(thinkingContent);
}
```

### 5. 工具调用显示

**工具状态**：
- `running` - 执行中（橙色动画）
- `done` - 完成（绿色）
- `error` - 失败（红色）

**渲染逻辑**：
```javascript
// 检测工具调用
if (item.type === 'tool_call') {
  renderToolCall(item.name, item.input, 'running');
}

// 检测工具结果
if (item.type === 'tool_result') {
  renderToolResult(item.result, 'done');
}
```

### 6. 图片上传

**流程**：
```
1. 用户选择图片
   ↓
2. 压缩图片（最大 10MB）
   ↓
3. 转换为 base64
   ↓
4. POST /api/upload → server.py
   ↓
5. server.py 保存到 /media/inbound/
   ↓
6. 返回 file:// 路径
   ↓
7. 通过 chat.send 发送给 Gateway
```

**server.py 实现**：
```python
def _handle_upload(self, content_length):
    # 解析 base64 图片
    img_data = base64.b64decode(img_base64)
    
    # 保存到 inbound 目录
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(INBOUND_DIR, filename)
    
    with open(filepath, 'wb') as f:
        f.write(img_data)
    
    # 返回 file:// 路径
    return {"path": f"file://{filepath}"}
```

### 7. 自动重连

**实现原理**：
```javascript
// WebSocket 关闭时自动重连
this.ws.onclose = (event) => {
  this.connected = false;
  this.onDisconnect?.(event.code, event.reason);
  
  // 3 秒后重连
  this.reconnectTimer = setTimeout(() => {
    this.connect();
  }, 3000);
};
```

### 8. 登录持久化

**LocalStorage 存储**：
```javascript
function saveLoginState(wsUrl, token, sessionKey) {
  const state = {
    wsUrl: wsUrl,
    token: token,
    sessionKey: sessionKey,
    timestamp: Date.now()
  };
  localStorage.setItem('oc_login_state', JSON.stringify(state));
}

function loadLoginState() {
  const state = JSON.parse(localStorage.getItem('oc_login_state'));
  if (!state) return null;
  
  // 检查是否过期（1小时）
  if (Date.now() - state.timestamp > 60 * 60 * 1000) {
    localStorage.removeItem('oc_login_state');
    return null;
  }
  
  return state;
}
```

## 配置系统

### config.js (前端配置)

```javascript
const OPENCLAW_CONFIG = {
  gateway: {
    defaultWsUrl: 'ws://your-gateway:18789/',
    defaultToken: 'YOUR_TOKEN',
    defaultSessionKey: 'agent:main:main',
  },
  cloudForward: {
    enabled: true,
    domainPattern: '.your-cloud.com',
    mapping: { 'http-domain': 'wss-domain' }
  },
  tailscale: {
    enabled: true,
    domainPattern: '.tailXXXX.ts.net',
    wsPort: 18789
  },
  ui: {
    loginExpiryMs: 60 * 60 * 1000,  // 1小时
    maxHistory: 100,
  }
};
```

### server_config.py (后端配置)

```python
PORT = 8080
BIND_HOST = '0.0.0.0'
TAILSCALE_DOMAIN = 'your-domain'
GATEWAY_HTTP = 'http://127.0.0.1:18789'
WORKSPACE_DIR = '/path/to/workspace'
MEDIA_DIR = '/path/to/media'
```

## 与 Gateway 的交互

### WebSocket API

| 方法 | 参数 | 说明 |
|------|------|------|
| `connect` | `auth.token` | 认证连接 |
| `chat.send` | `message, attachments` | 发送消息 |
| `chat.history` | `sessionKey, limit` | 获取历史 |
| `chat.abort` | - | 中止生成 |

### 事件类型

| 事件 | 说明 |
|------|------|
| `connect.challenge` | 认证挑战 |
| `hello` | 连接成功 |
| `chat.message` | 聊天消息（流式） |

### 认证流程

```
┌──────────┐                    ┌──────────┐
│  Client  │                    │ Gateway  │
└────┬─────┘                    └────┬─────┘
     │  WebSocket 连接               │
     │ ─────────────────────────────►│
     │                               │
     │  connect.challenge (nonce)    │
     │ ◄─────────────────────────────│
     │                               │
     │  { method: "connect",         │
     │    auth: { token: "xxx" } }   │
     │ ─────────────────────────────►│
     │                               │
     │  hello-ok / hello             │
     │ ◄─────────────────────────────│
     │                               │
     │  认证成功                       │
     │                               │
```

## HTTP API (server.py)

### 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Dashboard |
| `/mobile.html` | GET | Mobile 界面 |
| `/browse/` | GET | 文件浏览 |
| `/media/` | GET | 媒体文件 |
| `/api/*` | * | 代理到 Gateway |
| `/api/upload` | POST | 图片上传 |

### 代理逻辑

```python
def _handle_get_proxy(self):
    url = GATEWAY_HTTP + self.path[4:]  # /api/xxx -> http://gateway/xxx
    req = urllib.request.Request(url, method="GET")
    
    # 转发请求头
    for k in self.headers.keys():
        if k.lower() not in ["host", "connection"]:
            req.add_header(k, self.headers[k])
    
    response = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
    # 返回响应
```

## 安全考虑

### 1. Token 保护

- Token 存储在 `config.js`（不进入 Git）
- LocalStorage 存储有过期时间（1小时）
- HTTPS 环境下更安全

### 2. CORS 配置

Gateway 需要配置 `allowedOrigins`：

```json
{
  "gateway": {
    "controlUi": {
      "allowedOrigins": [
        "http://localhost:8080",
        "http://your-domain:8080"
      ]
    }
  }
}
```

### 3. 敏感信息

| 文件 | 内容 | Git |
|------|------|-----|
| `config.js` | Token, 域名 | ❌ 不进入 |
| `server_config.py` | IP, 域名 | ❌ 不进入 |
| `config.example.js` | 配置模板 | ✅ 进入 |
| `server_config.example.py` | 配置模板 | ✅ 进入 |

## 性能优化

### 1. 消息渲染

- 使用 `requestAnimationFrame` 优化流式输出
- 虚拟滚动（历史消息过多时）
- 延迟加载图片

### 2. 网络优化

- WebSocket 长连接，避免频繁握手
- 图片压缩（最大 10MB）
- 请求超时控制（30秒）

### 3. 内存优化

- 消息数量限制（`maxHistory: 100`）
- 及时清理 DOM
- 避免内存泄漏（事件监听器）

## 浏览器兼容性

| 浏览器 | 最低版本 |
|--------|----------|
| Chrome | 80+ |
| Safari | 13+ |
| Firefox | 75+ |
| Edge | 80+ |

**依赖的 API**：
- WebSocket
- LocalStorage
- Fetch API
- CSS Grid/Flexbox
- CSS Variables

## 扩展性

### 添加新消息类型

```javascript
// 在 handleMessage 中添加
if (msg.type === 'event' && msg.event === 'custom.event') {
  handleCustomEvent(msg.payload);
}
```

### 添加新工具显示

```javascript
// 在渲染逻辑中添加
if (item.type === 'tool_call' && item.name === 'my_tool') {
  renderCustomTool(item);
}
```

### 添加新配置项

```javascript
// config.js
const OPENCLAW_CONFIG = {
  // ...
  custom: {
    myOption: 'value'
  }
};
```

## 故障排查

### WebSocket 连接失败

```bash
# 检查 Gateway 运行状态
openclaw gateway status

# 检查端口
netstat -an | grep 18789

# 测试 WebSocket
wscat -c ws://localhost:18789
```

### 认证失败

```bash
# 检查 Token
cat ~/.openclaw/openclaw.json | jq '.gateway.auth.token'

# 检查 allowedOrigins
cat ~/.openclaw/openclaw.json | jq '.gateway.controlUi.allowedOrigins'
```

### 图片上传失败

```bash
# 检查目录权限
ls -la /root/.openclaw/media/inbound

# 检查 server.py 日志
journalctl --user -u openclaw-web -f
```

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v1.0.0 | 2026-03-01 | 初始版本 |
| - | - | WebSocket 客户端 |
| - | - | 流式输出渲染 |
| - | - | 思考过程显示 |
| - | - | 工具调用显示 |
| - | - | 图片上传 |
| - | - | 自动重连 |
| - | - | 登录持久化 |
| - | - | 配置分离 |
