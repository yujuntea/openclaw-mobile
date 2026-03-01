#!/usr/bin/env python3
"""
OpenClaw Mobile Server 配置模板

使用方法：
1. 复制此文件为 server_config.py
   cp server_config.example.py ../server_config.py
   
2. 修改配置值
   vim ../server_config.py

注意：server_config.py 包含敏感信息，不会进入 Git
"""

# ===========================================
# 服务器配置
# ===========================================

# 监听端口
PORT = 8080

# 监听地址
# 建议：
# - 内网 IP：'192.168.x.x' 或 '100.x.x.x'（Tailscale）
# - 本地开发：'127.0.0.1'
# - 所有接口：'0.0.0.0'（需要防火墙保护）
BIND_HOST = '0.0.0.0'

# 域名（用于显示访问地址）
# 建议：使用你的 Tailscale 域名或公网域名
TAILSCALE_DOMAIN = 'your-gateway-host.example.com'

# ===========================================
# Gateway 配置
# ===========================================

# Gateway HTTP 地址
GATEWAY_HTTP = 'http://127.0.0.1:18789'

# ===========================================
# 目录配置
# ===========================================

import os

# 工作目录
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

# Dashboard 目录（OpenClaw 安装目录）
# 修改为你的 OpenClaw 安装路径
DASHBOARD_DIR = '/path/to/openclaw/dist/control-ui'

# 媒体目录
MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media')

# 入站文件目录
INBOUND_DIR = os.path.join(MEDIA_DIR, 'inbound')

# ===========================================
# 其他配置
# ===========================================

# 请求超时（秒）
REQUEST_TIMEOUT = 30

# 最大请求大小（字节）
MAX_REQUEST_SIZE = 50 * 1024 * 1024  # 50MB

# 可浏览的目录
BROWSABLE_DIRS = {
    'media': MEDIA_DIR,
    'workspace': WORKSPACE_DIR,
}
