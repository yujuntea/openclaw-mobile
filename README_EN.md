**[中文文档](README.md)** | **English**

# OpenClaw Mobile

A modern, feature-rich mobile web interface for OpenClaw Gateway that provides seamless AI agent interaction on any device.

## Features

📱 **Mobile-First Design**
- Sleek dark theme with iOS-inspired aesthetics
- Touch-optimized interface with smooth animations
- Responsive layout that adapts to any screen size

🌐 **Multi-Language Support**
- Chinese (zh-CN) and English (en-US) built-in
- Easy language switching with one click
- Customizable app name for different languages
- Language preference saved to localStorage

💬 **Real-Time Communication**
- WebSocket-based streaming chat
- Display AI thinking process and reasoning
- Visual tool execution tracking
- Auto-reconnect on network changes

🔐 **Secure & Flexible Authentication**
- Token-based authentication
- Login state persistence (configurable expiry)
- Support for multiple environments (local, Tailscale, cloud)

🔌 **Multi-Environment Support**
- Automatic WebSocket URL detection
- Tailscale VPN integration
- Cloud port forwarding support (Tencent Cloud, etc.)
- Configurable domain mappings

📁 **Built-in Features**
- File browser for media and workspace
- Navigation menu with quick access
- Chat history persistence
- Image preview and gallery view

⚙️ **Customizable**
- App name and description
- WebSocket URL and token
- UI preferences
- All via config file

🛡️ **Production Ready**
- Clean separation of sensitive configurations
- Comprehensive security documentation
- Easy deployment with standalone Python server
- Systemd service integration

## Quick Start

### 1. Configuration

```bash
# Clone the repository
git clone https://github.com/yujuntea/openclaw-mobile.git
cd openclaw-mobile

# Create frontend config
cp config.example.js ../config.js

# Create backend config
cp server_config.example.py ../server_config.py

# Edit frontend config
vim ../config.js

# Edit backend config
vim ../server_config.py
```

### 2. Frontend Config (config.js)

```javascript
const OPENCLAW_CONFIG = {
  // App customization
  app: {
    appName: '小强 AI',           // Chinese name
    appNameEn: 'XiaoQiang AI',   // English name
    appDesc: 'AI 家庭助手',
    appDescEn: 'AI Family Assistant',
  },
  
  gateway: {
    // Your Gateway WebSocket URL
    defaultWsUrl: 'ws://your-gateway:18789/',
    
    // Your Gateway Token
    // Get it from: cat ~/.openclaw/openclaw.json | jq -r '.gateway.auth.token'
    defaultToken: 'YOUR_GATEWAY_TOKEN_HERE',
  },
  
  // If using cloud port forwarding, configure domain mapping
  cloudForward: {
    mapping: {
      'your-http-domain.example.com': 'your-wss-domain.example.com',
    }
  }
};
```

### 3. Backend Config (server_config.py)

```python
# Listen address
BIND_HOST = '0.0.0.0'  # or internal IP

# Domain (for display)
TAILSCALE_DOMAIN = 'your-gateway-host.example.com'

# Gateway HTTP address
GATEWAY_HTTP = 'http://127.0.0.1:18789'

# Dashboard directory
DASHBOARD_DIR = '/path/to/openclaw/dist/control-ui'
```

### 4. Configure Gateway

Edit `~/.openclaw/openclaw.json`:

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

### 5. Start Service

#### Foreground (Debug)

```bash
# Create symbolic links (recommended)
ln -sf $(pwd)/server.py ../server.py
ln -sf $(pwd)/mobile.html ../mobile.html

# Start in foreground
cd ..
python3 server.py
```

#### Background (Production)

**Option 1: nohup**

```bash
cd /path/to/workspace
nohup python3 server.py > server.log 2>&1 &

# View logs
tail -f server.log

# Stop service
pkill -f "python3 server.py"
```

**Option 2: Systemd (Recommended)**

**Step 1: Create Service File**

```bash
# Create directory
mkdir -p ~/.config/systemd/user

# Create service file
cat > ~/.config/systemd/user/openclaw-web.service << 'EOF'
[Unit]
Description=OpenClaw Web Server (Dashboard + Mobile + Media)
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/workspace
ExecStart=/usr/bin/python3 /path/to/workspace/server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

# Note: Change WorkingDirectory and ExecStart to your actual paths
```

**Step 2: Start Service**

```bash
# Reload config
systemctl --user daemon-reload

# Start service
systemctl --user start openclaw-web

# Enable on boot
systemctl --user enable openclaw-web
```

**Step 3: Manage Service**

```bash
# Check status
systemctl --user status openclaw-web

# View logs
journalctl --user -u openclaw-web -f

# Stop service
systemctl --user stop openclaw-web

# Restart service
systemctl --user restart openclaw-web
```

Access at `http://localhost:8080/mobile.html`

## WebSocket URL Detection

mobile.html automatically detects the access environment and selects the correct WebSocket URL via `getWebSocketUrl()`:

```javascript
function getWebSocketUrl() {
  const currentHost = window.location.hostname;
  
  // 1. Cloud port forwarding detection (Tencent Cloud, etc.)
  if (cloudForward.enabled && currentHost.includes(cloudForward.domainPattern)) {
    // Use configured wsUrl first
    if (cloudForward.wsUrl) return cloudForward.wsUrl;
    // Fallback to wss://current-host/
    return `wss://${currentHost}/`;
  }
  
  // 2. Tailscale detection
  if (tailscale.enabled && currentHost.includes(tailscale.domainPattern)) {
    return `ws://${currentHost}:18789/`;
  }
  
  // 3. Default
  return gateway.defaultWsUrl;
}
```

### Configuration Example

```javascript
// config.js
const OPENCLAW_CONFIG = {
  gateway: {
    defaultWsUrl: 'ws://your-hostname.tailXXXX.ts.net:18789/',
    // ...
  },
  cloudForward: {
    enabled: true,
    domainPattern: '.orcaterm.cloud.tencent.com',
    wsUrl: 'wss://forward-wss-xxx.orcaterm.cloud.tencent.com/'
  },
  tailscale: {
    enabled: true,
    domainPattern: '.tailXXXX.ts.net',
    wsPort: 18789
  }
};
```

### Detection Logic Flow

```
Access Domain Detection
    │
    ├─ Contains cloud forwarding domain (e.g., .orcaterm.cloud.tencent.com)?
    │       │
    │       ├─ cloudForward.wsUrl configured?
    │       │       └─ YES → Use cloudForward.wsUrl
    │       │                e.g., wss://forward-wss-xxx.orcaterm.cloud.tencent.com/
    │       │
    │       └─ NO → Use wss://current-host/
    │
    ├─ Contains Tailscale domain (e.g., .tailXXXX.ts.net)?
    │       └─ YES → Use ws://current-host:18789/
    │
    └─ Other environments
            └─ Use gateway.defaultWsUrl
```

### Configuration for Different Environments

| Access Method | HTTP Address | WebSocket Address | Config |
|---------------|--------------|-------------------|--------|
| Tailscale | `http://host.tailXXX.ts.net:8080` | `ws://host.tailXXX.ts.net:18789/` | `tailscale.wsPort` |
| Cloud Forward | `https://forward-xxx.orcaterm...` | `wss://forward-wss-...` | `cloudForward.wsUrl` |
| Local Dev | `http://localhost:8080` | `ws://localhost:18789/` | `gateway.defaultWsUrl` |

## Tailscale Configuration

If using Tailscale for internal network access, configure the following:

### 1. Frontend Config (config.js)

```javascript
tailscale: {
  enabled: true,
  domainPattern: '.tailXXXX.ts.net',  // Your Tailscale domain suffix
  wsPort: 18789  // Gateway WebSocket port
}
```

### 2. Backend Config (server_config.py)

```python
# Bind to Tailscale IP (recommended)
BIND_HOST = '100.x.x.x'  # Your Tailscale IP

# Or bind to all interfaces (requires firewall protection)
# BIND_HOST = '0.0.0.0'

TAILSCALE_DOMAIN = 'your-hostname.tailXXXX.ts.net'
```

### 3. Gateway Config (openclaw.json)

```json
{
  "gateway": {
    "controlUi": {
      "allowedOrigins": [
        "http://your-hostname.tailXXXX.ts.net:8080",
        "http://your-hostname.tailXXXX.ts.net"
      ]
    }
  }
}
```

### 4. Get Tailscale Info

```bash
# View Tailscale IP
tailscale ip

# View Tailscale domain
tailscale status
```

## Gateway allowedOrigins

Add all access domains in `openclaw.json`:

```json
{
  "gateway": {
    "controlUi": {
      "allowedOrigins": [
        "http://localhost:8080",
        "http://localhost:18789",
        "http://your-hostname.tailXXXX.ts.net:8080",
        "http://your-hostname.tailXXXX.ts.net",
        "https://your-https-domain.example.com"
      ]
    }
  }
}
```

## Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `config.js` | Frontend config | Parent directory |
| `server_config.py` | Backend config | Parent directory |
| `config.example.js` | Frontend template | Project directory |
| `server_config.example.py` | Backend template | Project directory |
| `i18n.js` | Internationalization | Project directory |

**Note**: `config.js` and `server_config.py` contain sensitive info and won't be tracked by Git.

## 🌐 Multi-Language Support

OpenClaw Mobile supports multiple languages with easy switching.

### Supported Languages

| Language | Code | Status |
|----------|------|--------|
| 中文 | `zh-CN` | ✅ Built-in |
| English | `en-US` | ✅ Built-in |

### Language Switching

- Click the language button in the header (shows "EN" or "中")
- Language preference is saved to localStorage
- UI updates instantly without page reload

### Customizing App Name

You can customize the app name for different languages in `config.js`:

```javascript
const OPENCLAW_CONFIG = {
  app: {
    appName: '我的助手',         // Chinese name
    appNameEn: 'My Assistant', // English name
  }
};
```

### Adding New Languages

To add a new language, edit `i18n.js`:

```javascript
languages: {
  'zh-CN': { ... },
  'en-US': { ... },
  'ja-JP': {  // Japanese
    appName: 'AIアシスタント',
    appDesc: 'AIアシスタント',
    // ... add other translations
  }
}
```

## Documentation

- [Deployment Guide](docs/DEPLOYMENT.md)
- [Configuration Reference](docs/CONFIGURATION.md)
- [Security Best Practices](docs/SECURITY.md)
- [Architecture](docs/ARCHITECTURE.md) - Technical implementation details

## Architecture

### Overview

```
┌──────────────┐     WebSocket      ┌──────────────────┐
│  mobile.html │ ◄─────────────────► │  OpenClaw Gateway │
│  (Frontend)  │                     │  (WebSocket)      │
└──────┬───────┘                     └──────────────────┘
       │
       │ HTTP (Image Upload)
       ▼
┌──────────────┐     HTTP Proxy      ┌──────────────────┐
│  server.py   │ ──────────────────► │  OpenClaw Gateway │
│  (Backend)   │                     │  (HTTP API)       │
└──────────────┘                     └──────────────────┘
```

### Core Features

| Feature | Implementation | Description |
|---------|---------------|-------------|
| Real-time Chat | WebSocket | Bidirectional communication with Gateway |
| Streaming Output | Event stream | Typewriter effect, real-time display |
| Thinking Process | Custom render | Purple background + left border |
| Tool Calls | Status render | Orange(running), Green(done), Red(error) |
| Image Upload | HTTP POST → Gateway | Compression + base64 encoding |
| Auto Reconnect | setTimeout(3s) | Automatic reconnection on disconnect |
| Login Persistence | LocalStorage | 1-hour session |
| Domain Detection | JS auto-detect | Tailscale, cloud port forwarding support |

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Vanilla JavaScript + WebSocket API + CSS3 |
| Backend | Python http.server + urllib |
| Communication | WebSocket (real-time) + HTTP (files) |
| Storage | LocalStorage (login state) |

### Core Modules

| Module | Responsibility |
|--------|---------------|
| `GwClient` | WebSocket client, manages connection, auth, messages |
| `handleMessage` | Message handler, processes res/event messages |
| `renderMessage` | Message rendering, supports text, thinking, tool calls |
| `renderThinking` | Thinking process rendering, streaming display |
| `renderToolCall` | Tool call rendering, status animation |
| `uploadImage` | Image upload, compression + base64 encoding |

### Gateway Integration

**WebSocket API**:

| Method | Description |
|--------|-------------|
| `connect` | Authenticate connection |
| `chat.send` | Send message |
| `chat.history` | Get history |
| `chat.abort` | Abort generation |

**Auth Flow**:
```
WebSocket connect → connect.challenge → send token → hello-ok → Auth success
```

**Message Format**:
```javascript
{
  type: 'event',
  event: 'chat.message',
  payload: {
    content: [
      { type: 'text', text: '...' },
      { type: 'thinking', thinking: '...' },
      { type: 'tool_call', name: '...', input: {...} }
    ]
  }
}
```

For detailed architecture, see [Architecture](docs/ARCHITECTURE.md).

## Requirements

- OpenClaw Gateway running on port 18789
- Python 3.7+ (for server.py)
- Modern web browser with WebSocket support

## License

GNU General Public License v3.0

---

Made with ❤️ for the OpenClaw community
