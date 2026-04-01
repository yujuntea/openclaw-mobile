#!/usr/bin/env python3
"""
OpenClaw Mobile Server - 统一的 Web 服务
- Dashboard 静态文件
- mobile.html
- media 文件服务
- 目录浏览功能

配置：从 server_config.py 读取配置
"""
import http.server
import socketserver
import urllib.request
import urllib.error
from urllib.parse import unquote
import json
import os
import sys
import uuid
import base64
import time
import re
import html as html_module
import secrets

# ==================== Session Manager ====================
class SessionManager:
    """Session 管理器 - 用于用户认证"""
    
    def __init__(self):
        self.sessions = {}  # oc_session_token -> session_data
        self.token_lifetime = 3600 * 24  # 24小时有效期
    
    def create_session(self, gateway_token, client_ip):
        """创建新 session"""
        oc_session_token = secrets.token_urlsafe(32)
        self.sessions[oc_session_token] = {
            'created_at': time.time(),
            'gateway_token': gateway_token,
            'ip': client_ip,
            'last_used': time.time(),
        }
        return oc_session_token
    
    def verify_session(self, oc_session_token, client_ip):
        """验证 session 是否有效"""
        if not oc_session_token or oc_session_token not in self.sessions:
            return False
        
        session = self.sessions[oc_session_token]
        
        # 检查是否过期
        if time.time() - session['created_at'] > self.token_lifetime:
            del self.sessions[oc_session_token]
            return False
        
        # 更新最后使用时间
        session['last_used'] = time.time()
        return True
    
    def get_gateway_token(self, oc_session_token):
        """获取 session 对应的 gateway token"""
        if oc_session_token in self.sessions:
            return self.sessions[oc_session_token]['gateway_token']
        return None
    
    def cleanup_expired(self):
        """清理过期 session"""
        now = time.time()
        expired = [
            token for token, data in self.sessions.items()
            if now - data['created_at'] > self.token_lifetime
        ]
        for token in expired:
            del self.sessions[token]

# 全局 Session Manager 实例
session_manager = SessionManager()

# 添加配置文件搜索路径
# 注意：敏感配置文件（server_config.py）只在 workspace 目录下
# 非敏感文件（i18n.js, mobile.html 等）从脚本目录提供
_config_paths = [
    os.path.expanduser('~/.openclaw/workspace'),  # 用户 workspace 目录（配置文件位置）
    os.path.dirname(os.path.realpath(__file__)),  # 脚本所在目录 (openclaw-mobile-release)
]
for _path in _config_paths:
    if _path not in sys.path:
        sys.path.insert(0, _path)

# 尝试从 server_config.py 读取配置
try:
    from server_config import (
        PORT, BIND_HOST, TAILSCALE_DOMAIN,
        GATEWAY_HTTP, WORKSPACE_DIR, MEDIA_DIR, 
        INBOUND_DIR, DASHBOARD_DIR,
        REQUEST_TIMEOUT, MAX_REQUEST_SIZE, BROWSABLE_DIRS
    )
    import sys; sys.stderr.write(f"[Config] Loaded from server_config.py: BIND_HOST={BIND_HOST}")
except ImportError as e:
    import sys; sys.stderr.write(f"[Config] server_config.py not found, using defaults: {e}")
    # 如果没有配置文件，使用默认值
    PORT = 8080
    BIND_HOST = '127.0.0.1'  # 默认仅本机访问（安全）
    TAILSCALE_DOMAIN = 'localhost'
    GATEWAY_HTTP = 'http://127.0.0.1:18789'
    # 计算工作目录（处理符号链接）
    _script_path = os.path.realpath(__file__)  # 解析符号链接
    _script_dir = os.path.dirname(_script_path)
    
    # 如果在 openclaw-mobile-release 目录中，使用父目录作为 workspace
    if _script_dir.endswith('openclaw-mobile-release'):
        WORKSPACE_DIR = os.path.dirname(_script_dir)
    else:
        WORKSPACE_DIR = _script_dir
    
    MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media')
    INBOUND_DIR = os.path.join(MEDIA_DIR, 'inbound')
    DASHBOARD_DIR = os.path.join(_script_dir, 'dashboard')
    REQUEST_TIMEOUT = 30
    MAX_REQUEST_SIZE = 50 * 1024 * 1024

# 允许浏览的目录
BROWSABLE_DIRS = {
    'media': MEDIA_DIR,
    'workspace': WORKSPACE_DIR,
}


class ProxyServer(http.server.SimpleHTTPRequestHandler):
    """统一代理服务器"""
    
    protocol_version = 'HTTP/1.1'
    
    # 需要认证的路径
    PROTECTED_PATHS = [
        '/media/',
        '/api/upload',
        '/api/command',
        '/api/sessions',
    ]
    
    # 公开路径（不需要认证）
    PUBLIC_PATHS = [
        ## '/' removed - matches all paths! # FIXED
        '/mobile.html',
        '/config.js',
        '/i18n.js',
        '/api/login',
        '/api/health',
        '/api/config',
        '/api/models',
        '/api/model',
        '/dashboard/',
        '/browse/',  # 文件浏览（公开访问）
    ]
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        import sys
        sys.stderr.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {self.address_string()} - {format % args}\n")
        sys.stderr.flush()
    
    def _get_cookie(self, name):
        """获取 cookie 值"""
        cookies = self.headers.get('Cookie', '')
        for cookie in cookies.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                if key == name:
                    return value
        return None
    
    def _check_auth(self):
        """检查请求是否已认证"""
        # 公开路径直接放行
        for path in self.PUBLIC_PATHS:
            if self.path == path or self.path.startswith(path):
                return True
        
        # 检查是否需要认证
        needs_auth = any(self.path.startswith(p) for p in self.PROTECTED_PATHS)
        if not needs_auth:
            return True
        
        # 获取 session token 或 gateway token
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            oc_session_token = auth_header[7:]
        else:
            # 也支持从 cookie 获取
            oc_session_token = self._get_cookie('oc_session_token')
        
        # 验证 session
        client_ip = self.client_address[0]
        self.log_message("[Auth] 验证 session: token=%s, ip=%s", oc_session_token[:20] if oc_session_token else 'None', client_ip)
        if oc_session_token and session_manager.verify_session(oc_session_token, client_ip):
            # 保存 gateway_token 供后续使用
            self.gateway_token = session_manager.get_gateway_token(oc_session_token)
            self.log_message("[Auth] 验证成功")
            return True
        
        # 也支持直接从 X-Gateway-Token 请求头获取
        gateway_token = self.headers.get('X-Gateway-Token', '')
        if gateway_token:
            self.log_message("[Auth] 使用 X-Gateway-Token: %s", gateway_token[:20])
            if self._verify_gateway_token(gateway_token):
                self.gateway_token = gateway_token
                self.log_message("[Auth] X-Gateway-Token 验证成功")
                return True
        
        self.log_message("[Auth] 验证失败")
        # 未认证，返回 401
        self._send_json_response(401, {'error': 'Unauthorized', 'message': '请先登录'})
        return False
    
    def handle_one_request(self):
        """重写以添加超时控制"""
        self.connection.settimeout(REQUEST_TIMEOUT)
        try:
            return http.server.SimpleHTTPRequestHandler.handle_one_request(self)
        except socket.timeout:
            self.log_message("Request timeout")
            self.close_connection = True
        except Exception as e:
            self.log_message("Error: %s", str(e))
            self.close_connection = True
    
    def do_GET(self):
        """处理 GET 请求"""
        # 配置 API（公开）- 在代理之前处理
        if self.path == '/api/config':
            self._handle_config()
            return
        
        # Health API（公开）
        if self.path == '/api/health':
            self._send_json_response(200, {'status': 'ok', 'timestamp': time.time()})
            return
        
        # 模型列表 API（公开）
        if self.path == '/api/models':
            self._handle_models()
            return
        
        # Sessions 列表 API（需要认证）
        if self.path == '/api/sessions':
            if not self._check_auth():
                return
            self._handle_sessions_list()
            return
        
        # API 代理
        if self.path.startswith('/api/'):
            self._handle_get_proxy()
            return
        
        # Media 文件服务（需要认证）
        if self.path.startswith('/media/'):
            if not self._check_auth():
                return
            self._serve_media_file(self.path[7:])
            return
        
        # 目录浏览（公开访问，已在 PUBLIC_PATHS 中配置）
        if self.path.startswith('/browse/'):
            self._serve_directory_listing(self.path[8:])
            return
        
        # Dashboard 静态文件
        if self.path.startswith('/assets/'):
            self._serve_dashboard_file(self.path[1:])
            return
        
        if self.path in ['/favicon.svg', '/favicon-32.png', '/favicon.ico', '/apple-touch-icon.png']:
            self._serve_dashboard_file(self.path[1:])
            return

        # Mobile 相关静态文件（从 openclaw-mobile-release 目录提供）
        # 注意：必须包含 '/' 和 '/index.html' 的重定向
        request_path = self.path
        if request_path == '/' or request_path == '/index.html':
            request_path = '/mobile.html'
        
        mobile_files = ['/mobile.html', '/config.js', '/i18n.js']
        if request_path in mobile_files or request_path.startswith('/screenshots/'):
            # 直接调用 _serve_mobile_file
            relative_path = request_path[1:]  # 去掉开头的 /
            
            # 配置逻辑：
            # - config.js: 从 workspace 目录读取（配置文件，用户可自定义）
            # - i18n.js, mobile.html: 从脚本目录读取（工程文件）
            # - screenshots: 从脚本目录读取
            if relative_path == 'config.js':
                # config.js 从 workspace 目录提供（配置文件位置）
                filepath = os.path.join(WORKSPACE_DIR, relative_path)
            else:
                # 其他文件从脚本目录提供
                mobile_dir = os.path.dirname(os.path.realpath(__file__))
                filepath = os.path.join(mobile_dir, relative_path)
            
            if os.path.exists(filepath):
                mime_types = {
                    '.html': 'text/html; charset=utf-8',
                    '.js': 'application/javascript; charset=utf-8',
                    '.css': 'text/css',
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.svg': 'image/svg+xml',
                    '.ico': 'image/x-icon',
                }
                ext = os.path.splitext(relative_path)[1].lower()
                mime_type = mime_types.get(ext, 'application/octet-stream')
                
                with open(filepath, 'rb') as f:
                    content = f.read()
                
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", len(content))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_error(404, "File not found")
                return

        # 其他静态文件
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        """处理 POST 请求"""
        content_length = int(self.headers.get('Content-Length', 0))
        
        # 检查请求大小
        if content_length > MAX_REQUEST_SIZE:
            self.send_error(413, "Request too large")
            return
        
        # 登录 API（公开）
        if self.path == '/api/login':
            self._handle_login(content_length)
            return
        
        # 命令执行 API（需要认证）
        if self.path == '/api/command':
            if not self._check_auth():
                return
            self._handle_command(content_length)
            return
        
        # 切换模型 API（公开）
        if self.path == '/api/model':
            self._handle_model_switch(content_length)
            return
        
        # 图片上传 API（需要认证）
        if self.path == '/api/upload':
            if not self._check_auth():
                return
            self._handle_upload(content_length)
            return
        
        # API 代理
        if self.path.startswith('/api/'):
            self._handle_api_proxy(content_length)
            return
        
        self.send_error(404, "Not Found")
    
    def _serve_dashboard_file(self, relative_path):
        """提供 Dashboard 静态文件"""
        try:
            filepath = os.path.join(DASHBOARD_DIR, relative_path)
            if not os.path.exists(filepath):
                self.send_error(404, "File not found")
                return
            
            # 确定 MIME 类型
            mime_types = {
                '.html': 'text/html',
                '.js': 'application/javascript',
                '.css': 'text/css',
                '.png': 'image/png',
                '.svg': 'image/svg+xml',
                '.ico': 'image/x-icon',
            }
            ext = os.path.splitext(relative_path)[1].lower()
            mime_type = mime_types.get(ext, 'application/octet-stream')
            
            with open(filepath, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", len(content))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
            
        except Exception as e:
            self.log_message("Dashboard file error: %s", str(e))
            self.send_error(500, str(e))
    
    def _serve_mobile_file(self, relative_path):
        """提供 Mobile 页面相关静态文件（从 openclaw-mobile-release 目录）"""
        try:
            # 计算 openclaw-mobile-release 目录路径
            mobile_dir = os.path.dirname(os.path.realpath(__file__))
            filepath = os.path.join(mobile_dir, relative_path)
            
            if not os.path.exists(filepath):
                self.send_error(404, "File not found")
                return
            
            # 安全检查：确保文件在 mobile_dir 内
            if not os.path.abspath(filepath).startswith(os.path.abspath(mobile_dir)):
                self.send_error(403, "Forbidden")
                return
            
            # 确定 MIME 类型
            mime_types = {
                '.html': 'text/html; charset=utf-8',
                '.js': 'application/javascript; charset=utf-8',
                '.css': 'text/css',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.svg': 'image/svg+xml',
                '.ico': 'image/x-icon',
            }
            ext = os.path.splitext(relative_path)[1].lower()
            mime_type = mime_types.get(ext, 'application/octet-stream')
            
            with open(filepath, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", len(content))
            self.send_header("Access-Control-Allow-Origin", "*")
            # 禁止缓存，确保用户总是获取最新版本
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(content)
            
        except Exception as e:
            self.log_message("Mobile file error: %s", str(e))
            self.send_error(500, str(e))
    
    def _serve_media_file(self, relative_path):
        """提供 Media 文件"""
        try:
            # 安全检查：防止目录遍历
            if '..' in relative_path:
                self.send_error(403, "Forbidden")
                return
            
            filepath = os.path.join(MEDIA_DIR, relative_path)
            if not os.path.exists(filepath):
                self.send_error(404, "File not found")
                return
            
            # 确定 MIME 类型
            mime_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.mp4': 'video/mp4',
                '.webm': 'video/webm',
                '.pdf': 'application/pdf',
            }
            ext = os.path.splitext(relative_path)[1].lower()
            mime_type = mime_types.get(ext, 'application/octet-stream')
            
            with open(filepath, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", len(content))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "max-age=3600")
            self.end_headers()
            self.wfile.write(content)
            
        except Exception as e:
            self.log_message("Media file error: %s", str(e))
            self.send_error(500, str(e))
    
    def _serve_directory_listing(self, path):
        self.log_message("DEBUG: path=%s", path)
        """提供目录列表"""
        try:
            # 解析路径: browse/media/xxx 或 browse/workspace/xxx
            parts = path.strip('/').split('/')
            
            # 解析查询参数（排序和方向）
            query_sort = 'mtime'  # 默认按修改时间排序
            query_order = 'desc'  # 默认降序（最新的在前）
            if '?' in parts[-1]:
                path_part, query = parts[-1].split('?', 1)
                parts[-1] = path_part
                for param in query.split('&'):
                    if param.startswith('sort='):
                        query_sort = param[5:]
                    elif param.startswith('order='):
                        query_order = param[6:]
            
            if not parts or parts[0] not in BROWSABLE_DIRS:
                self._serve_browse_root()
                return
            
            dir_name = parts[0]
            sub_path = '/'.join(parts[1:]) if len(parts) > 1 else ''
            base_dir = BROWSABLE_DIRS[dir_name]
            # URL解码支持中文文件名
            sub_path = unquote(sub_path)
            full_path = os.path.join(base_dir, sub_path) if sub_path else base_dir
            
            # 安全检查
            if '..' in path or not os.path.exists(full_path):
                self.send_error(404, "Not found")
                return
            
            # 检查是否是文件
            if os.path.isfile(full_path):
                self._serve_any_file(full_path)
                return
            
            # 检查是否是目录
            if not os.path.isdir(full_path):
                self.send_error(404, "Not found")
                return
            
            # 列出目录内容
            items = []
            try:
                for name in os.listdir(full_path):
                    item_path = os.path.join(full_path, name)
                    is_dir = os.path.isdir(item_path)
                    stat = os.stat(item_path)
                    items.append({
                        'name': name,
                        'is_dir': is_dir,
                        'size': stat.st_size if not is_dir else 0,
                        'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                        'mtime_ts': stat.st_mtime  # 用于排序
                    })
            except PermissionError:
                self.send_error(403, "Permission denied")
                return
            
            # 排序：目录优先，然后按指定字段排序
            dirs = [item for item in items if item['is_dir']]
            files = [item for item in items if not item['is_dir']]
            
            reverse = (query_order == 'desc')
            
            if query_sort == 'name':
                dirs.sort(key=lambda x: x['name'].lower(), reverse=reverse)
                files.sort(key=lambda x: x['name'].lower(), reverse=reverse)
            elif query_sort == 'size':
                dirs.sort(key=lambda x: x['name'].lower())
                files.sort(key=lambda x: x['size'], reverse=reverse)
            else:  # mtime (默认)
                dirs.sort(key=lambda x: x['name'].lower())
                files.sort(key=lambda x: x['mtime_ts'], reverse=reverse)
            
            items = dirs + files
            
            # 生成 HTML
            parent_path = '/browse/' + dir_name + ('/' + '/'.join(parts[1:-1]) if len(parts) > 2 else '')
            html = self._generate_dir_html(dir_name, sub_path, items, parent_path, query_sort, query_order)
            
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(html))
            self.end_headers()
            self.wfile.write(html)
            
        except Exception as e:
            self.log_message("Directory listing error: %s", str(e))
            self.send_error(500, str(e))
    
    def _serve_browse_root(self):
        """显示可浏览的目录列表"""
        html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文件浏览器</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a1a; color: #fff; margin: 0; padding: 20px; }
        h1 { color: #0a84ff; }
        .container { max-width: 800px; margin: 0 auto; }
        .dir-item { display: block; padding: 16px; margin: 8px 0; background: #2c2c2e; border-radius: 12px; color: #fff; text-decoration: none; transition: background 0.2s; }
        .dir-item:hover { background: #3a3a3c; }
        .dir-item .icon { font-size: 24px; margin-right: 12px; }
        .dir-item .name { font-size: 18px; font-weight: 500; }
        .dir-item .desc { color: #8e8e93; font-size: 14px; margin-top: 4px; }
        .nav { margin-bottom: 20px; }
        .nav a { color: #0a84ff; text-decoration: none; margin-right: 16px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📁 文件浏览器</h1>
        <div class="nav">
            <a href="/">🏠 Dashboard</a>
            <a href="/mobile.html">📱 Mobile</a>
        </div>
        <div class="dirs">
            <a href="/browse/media" class="dir-item">
                <span class="icon">🖼️</span>
                <span class="name">Media</span>
                <div class="desc">截图、图片、视频等媒体文件</div>
            </a>
            <a href="/browse/workspace" class="dir-item">
                <span class="icon">📂</span>
                <span class="name">Workspace</span>
                <div class="desc">工作目录文件</div>
            </a>
        </div>
    </div>
</body>
</html>'''
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(html.encode()))
        self.end_headers()
        self.wfile.write(html.encode())
    
    def _generate_dir_html(self, dir_name, sub_path, items, parent_path, sort_by='mtime', sort_order='desc'):
        """生成目录列表 HTML"""
        title = f"{dir_name}" + (f"/{sub_path}" if sub_path else "")
        
        # 计算排序箭头和状态
        def get_arrow(field):
            if sort_by != field: return '⬍'
            return '⬆' if sort_order == 'asc' else '⬇'
        def get_order(field):
            if sort_by != field: return 'desc'
            return 'asc' if sort_order == 'desc' else 'desc'
        def get_active(field):
            return 'active' if sort_by == field else ''
        
        name_arrow = get_arrow('name')
        size_arrow = get_arrow('size')
        mtime_arrow = get_arrow('mtime')
        name_order = get_order('name')
        size_order = get_order('size')
        mtime_order = get_order('mtime')
        name_active = get_active('name')
        size_active = get_active('size')
        mtime_active = get_active('mtime')
        
        items_html = ''
        # 父目录链接
        if sub_path:
            items_html += f'''<tr>
                <td><a href="{parent_path}" class="item dir">📁 ..</a></td>
                <td>-</td>
                <td>-</td>
            </tr>'''
        
        for item in items:
            item_path = f"/browse/{dir_name}/{sub_path}/{item['name']}" if sub_path else f"/browse/{dir_name}/{item['name']}"
            icon = '📁' if item['is_dir'] else self._get_file_icon(item['name'])
            size_str = self._format_size(item['size']) if not item['is_dir'] else '-'
            
            # 图片预览 - 使用正确的路径
            preview = ''
            if not item['is_dir'] and item['name'].lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                # 根据目录类型构建正确的图片路径
                if dir_name == 'media':
                    img_path = f"/media/{sub_path}/{item['name']}" if sub_path else f"/media/{item['name']}"
                else:
                    # 对于 workspace 等其他目录，使用 browse 路径
                    img_path = f"/browse/{dir_name}/{sub_path}/{item['name']}" if sub_path else f"/browse/{dir_name}/{item['name']}"
                preview = f'''<img src="{img_path}" class="preview" onclick="showImage(this.src)" alt="{item['name']}">'''
            
            items_html += f'''<tr>
                <td><a href="{item_path}" class="item {'dir' if item['is_dir'] else 'file'}">{icon} {html_module.escape(item['name'])}</a>{preview}</td>
                <td>{size_str}</td>
                <td>{item['mtime']}</td>
            </tr>'''
        
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_module.escape(title)}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a1a; color: #fff; margin: 0; padding: 20px; }}
        h1 {{ color: #0a84ff; word-break: break-all; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th {{ text-align: left; padding: 12px; border-bottom: 1px solid #3a3a3c; color: #8e8e93; white-space: nowrap; }}
        td {{ padding: 12px; border-bottom: 1px solid #2c2c2e; }}
        .item {{ color: #fff; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; }}
        .item:hover {{ color: #0a84ff; }}
        .item.dir {{ color: #0a84ff; }}
        .preview {{ max-width: 60px; max-height: 60px; border-radius: 8px; margin-left: 12px; cursor: pointer; vertical-align: middle; }}
        .nav {{ margin-bottom: 20px; }}
        .nav a {{ color: #0a84ff; text-decoration: none; margin-right: 16px; }}
        .overlay {{ position: fixed; inset: 0; background: rgba(0,0,0,0.9); display: none; align-items: center; justify-content: center; z-index: 1000; cursor: zoom-out; }}
        .overlay img {{ max-width: 95%; max-height: 95%; border-radius: 8px; }}
        .overlay.active {{ display: flex; }}
        .sort-link {{ color: #8e8e93; text-decoration: none; padding: 4px 8px; border-radius: 4px; }}
        .sort-link:hover {{ color: #0a84ff; background: rgba(10,132,255,0.1); }}
        .sort-link.active {{ color: #0a84ff; font-weight: 600; background: rgba(10,132,255,0.15); }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📁 {html_module.escape(title)}</h1>
        <div class="nav">
            <a href="/">🏠 Dashboard</a>
            <a href="/mobile.html">📱 Mobile</a>
            <a href="/browse/">📁 根目录</a>
        </div>
        <table>
            <thead>
                <tr>
                    <th><a href="?sort=name&order={name_order}" class="sort-link {name_active}">名称 {name_arrow}</a></th>
                    <th><a href="?sort=size&order={size_order}" class="sort-link {size_active}">大小 {size_arrow}</a></th>
                    <th><a href="?sort=mtime&order={mtime_order}" class="sort-link {mtime_active}">修改时间 {mtime_arrow}</a></th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>
    </div>
    <div class="overlay" id="overlay" onclick="this.classList.remove('active')">
        <img id="overlayImg" src="">
    </div>
    <script>
        function showImage(src) {{
            document.getElementById('overlayImg').src = src;
            document.getElementById('overlay').classList.add('active');
        }}
    </script>
</body>
</html>'''.encode('utf-8')
    
    def _get_file_icon(self, filename):
        """根据文件扩展名返回图标"""
        ext = os.path.splitext(filename)[1].lower()
        icons = {
            '.jpg': '🖼️', '.jpeg': '🖼️', '.png': '🖼️', '.gif': '🖼️', '.webp': '🖼️',
            '.mp4': '🎬', '.webm': '🎬', '.mov': '🎬',
            '.pdf': '📄', '.doc': '📄', '.docx': '📄',
            '.txt': '📝', '.md': '📝',
            '.json': '📋', '.xml': '📋',
            '.js': '💻', '.ts': '💻', '.py': '💻', '.sh': '💻',
            '.zip': '📦', '.tar': '📦', '.gz': '📦',
            '.log': '📊',
        }
        return icons.get(ext, '📄')
    
    def _format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
    
    def _serve_any_file(self, filepath):
        """提供任意文件下载"""
        try:
            # 确定 MIME 类型
            mime_types = {
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.gif': 'image/gif', '.webp': 'image/webp',
                '.mp4': 'video/mp4', '.webm': 'video/webm',
                '.pdf': 'application/pdf',
                '.txt': 'text/plain; charset=utf-8',
                '.md': 'text/markdown; charset=utf-8',
                '.json': 'application/json; charset=utf-8',
                '.xml': 'application/xml; charset=utf-8',
                '.html': 'text/html; charset=utf-8',
                '.css': 'text/css; charset=utf-8',
                '.js': 'application/javascript; charset=utf-8',
                '.py': 'text/x-python; charset=utf-8',
                '.sh': 'text/x-sh; charset=utf-8',
                '.yml': 'text/yaml; charset=utf-8',
                '.yaml': 'text/yaml; charset=utf-8',
                '.log': 'text/plain; charset=utf-8',
                '.csv': 'text/csv; charset=utf-8',
            }
            ext = os.path.splitext(filepath)[1].lower()
            mime_type = mime_types.get(ext, 'application/octet-stream')
            
            with open(filepath, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", len(content))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
            
        except Exception as e:
            self.log_message("File serve error: %s", str(e))
            self.send_error(500, str(e))
    
    def _handle_get_proxy(self):
        """处理 GET 代理请求"""
        try:
            url = GATEWAY_HTTP + self.path[4:]  # /api/xxx -> http://gateway/xxx
            req = urllib.request.Request(url, method="GET")
            
            # 转发请求头
            for k in self.headers.keys():
                if k.lower() not in ["host", "connection"]:
                    req.add_header(k, self.headers[k])
            
            response = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
            response_data = response.read()
            
            self.send_response(response.status)
            self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(response_data))
            self.end_headers()
            self.wfile.write(response_data)
            
        except urllib.error.HTTPError as e:
            error_data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(error_data))
            self.end_headers()
            self.wfile.write(error_data)
            
        except Exception as e:
            self.log_message("GET proxy error: %s", str(e))
            self._send_json_response(502, {"error": str(e)})
    
    def _handle_upload(self, content_length):
        """处理文件上传（支持图片和任意文件）"""
        try:
            content_type = self.headers.get('Content-Type', '')
            
            if 'multipart/form-data' in content_type:
                # Multipart 上传
                body = self.rfile.read(content_length)
                match = re.search(b'data:image/([^;]+);base64,([A-Za-z0-9+/=]+)', body)
                if match:
                    img_data = base64.b64decode(match.group(2))
                    ext = match.group(1).decode()
                    filename = f"{uuid.uuid4()}.{ext}"
                else:
                    self._send_json_response(400, {"error": "No image data found"})
                    return
            else:
                # JSON 格式上传
                body = self.rfile.read(content_length)
                data = json.loads(body)
                
                file_data = None
                filename = None
                original_name = None
                mime_type = None
                
                # 支持两种格式：
                # 1. { "image": "data:image/png;base64,..." } - 旧格式（图片）
                # 2. { "file": "data:application/pdf;base64,...", "filename": "doc.pdf" } - 新格式（任意文件）
                
                if 'file' in data:
                    # 新格式：任意文件
                    file_base64 = data['file']
                    original_name = data.get('filename', 'unknown')
                    mime_type = data.get('mimeType', 'application/octet-stream')
                    
                    if ',' in file_base64:
                        # data:xxx;base64,yyy 格式
                        header, file_base64 = file_base64.split(',', 1)
                        # 从 header 提取 mime type
                        if ':' in header and ';' in header:
                            mime_type = header.split(':')[1].split(';')[0]
                    
                    file_data = base64.b64decode(file_base64)
                    
                    # 确定文件扩展名
                    ext_map = {
                        'application/pdf': 'pdf',
                        'application/msword': 'doc',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
                        'application/vnd.ms-excel': 'xls',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
                        'application/vnd.ms-powerpoint': 'ppt',
                        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
                        'application/zip': 'zip',
                        'application/x-tar': 'tar',
                        'application/gzip': 'gz',
                        'text/plain': 'txt',
                        'text/markdown': 'md',
                        'text/csv': 'csv',
                        'application/json': 'json',
                        'application/xml': 'xml',
                        'text/html': 'html',
                        'text/css': 'css',
                        'application/javascript': 'js',
                        'text/x-python': 'py',
                        'text/x-sh': 'sh',
                    }
                    ext = ext_map.get(mime_type, original_name.rsplit('.', 1)[-1] if '.' in original_name else 'bin')
                    filename = f"{uuid.uuid4()}.{ext}"
                    
                elif 'image' in data:
                    # 旧格式：图片
                    img_base64 = data['image']
                    if ',' in img_base64:
                        img_base64 = img_base64.split(',')[1]
                    file_data = base64.b64decode(img_base64)
                    filename = f"{uuid.uuid4()}.jpg"
                    mime_type = 'image/jpeg'
                    original_name = filename
                
                if not file_data:
                    self._send_json_response(400, {"error": "No file data"})
                    return
            
            # 保存到 inbound 目录
            if not filename:
                filename = f"{uuid.uuid4()}.bin"
            filepath = os.path.join(INBOUND_DIR, filename)
            
            os.makedirs(INBOUND_DIR, exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(file_data)
            
            self._send_json_response(200, {
                "success": True,
                "path": filepath,
                "filename": filename,
                "originalName": original_name,
                "mimeType": mime_type,
                "size": len(file_data)
            })
            
        except Exception as e:
            self.log_message("Upload error: %s", str(e))
            self._send_json_response(500, {"error": str(e)})
    
    def _handle_api_proxy(self, content_length):
        """处理 API 代理请求"""
        try:
            body = self.rfile.read(content_length)
            
            hdrs = {"Content-Type": "application/json"}
            
            # 转发请求头
            for k in self.headers.keys():
                if k.lower() not in ["host", "connection", "content-length"]:
                    hdrs[k] = self.headers[k]
            
            auth = self.headers.get('Authorization', '')
            if auth:
                hdrs['Authorization'] = auth
            
            url = GATEWAY_HTTP + self.path[4:]  # /api/xxx -> http://gateway/xxx
            req = urllib.request.Request(url, data=body, method="POST", headers=hdrs)
            
            response = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
            response_data = response.read()
            
            self.send_response(response.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(response_data))
            self.end_headers()
            self.wfile.write(response_data)
            
        except urllib.error.HTTPError as e:
            error_data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(error_data))
            self.end_headers()
            self.wfile.write(error_data)
            
        except urllib.error.URLError as e:
            self.log_message("URL error: %s", str(e))
            self._send_json_response(502, {"error": f"Gateway error: {str(e)}"})
            
        except Exception as e:
            self.log_message("API proxy error: %s", str(e))
            self._send_json_response(500, {"error": str(e)})
    
    def _send_json_response(self, status, data):
        """发送 JSON 响应"""
        response = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(response))
        self.end_headers()
        self.wfile.write(response)
    
    def _get_whitelist_tokens(self):
        """从配置文件读取白名单 tokens
        
        搜索路径（按优先级）：
        1. ~/.openclaw/workspace/config.js（配置文件推荐位置）
        2. 工程目录/config.js（备选）
        """
        whitelist = []
        
        # 配置搜索路径
        config_paths = [
            os.path.join(WORKSPACE_DIR, 'config.js'),  # workspace 目录（推荐）
            os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.js')  # 工程目录
        ]
        
        for config_path in config_paths:
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_content = f.read()
                    
                    import re
                    
                    # 移除注释避免干扰
                    config_clean = re.sub(r'//.*?$', '', config_content, flags=re.MULTILINE)
                    config_clean = re.sub(r'/\*.*?\*/', '', config_clean, flags=re.DOTALL)
                    
                    # 匹配 defaultToken 格式
                    match = re.search(r"defaultToken\s*:\s*['\"]([^'\"]+)['\"]", config_clean)
                    if match:
                        token = match.group(1)
                        if token not in whitelist:
                            whitelist.append(token)
                            self.log_message("[Token验证] 从 %s 读取 token: %s", 
                                           config_path, token[:10]+'...')
                    else:
                        self.log_message("[Token验证] %s 中未找到 defaultToken", 
                                       os.path.basename(config_path))
            except Exception as e:
                self.log_message("[Token验证] 读取 %s 失败: %s", config_path, str(e))
        
        return whitelist
        
        return whitelist
    
    def _verify_gateway_token(self, token):
        """验证 Gateway token 是否有效
        
        验证策略（按优先级）：
        1. 白名单验证：从 config.js 读取有效 token
        2. 格式验证：检查 token 格式是否合法
        3. 长度检查：确保 token 长度合理
        """
        if not token:
            self.log_message("[Token验证] Token 为空")
            return False
        
        # 长度检查：太短的 token 直接拒绝
        if len(token) < 10:
            self.log_message("[Token验证] Token 太短: %d 字符", len(token))
            return False
        
        # 格式检查：只允许字母、数字、连字符、下划线
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', token):
            self.log_message("[Token验证] Token 包含非法字符")
            return False
        
        # 白名单验证
        whitelist = self._get_whitelist_tokens()
        if token in whitelist:
            self.log_message("[Token验证] ✅ Token 在白名单中")
            return True
        
        # 如果不在白名单中，检查是否是常见的测试 token 模式
        if token.startswith('test-') or token.startswith('mock-'):
            self.log_message("[Token验证] ❌ 测试 token 被拒绝")
            return False
        
        # 记录未授权的尝试（安全审计）
        self.log_message("[Token验证] ⚠️ Token 不在白名单中，长度: %d, 前5位: %s", 
                        len(token), token[:5])
        
        # 不在白名单中，默认拒绝（安全优先）
        return False
    
    def _handle_login(self, content_length):
        """处理登录请求"""
        try:
            content = self.rfile.read(content_length)
            data = json.loads(content.decode('utf-8'))
            gateway_token = data.get('token') or data.get('password')
            
            if not gateway_token:
                self._send_json_response(400, {'error': 'Token required', 'message': '请输入 Token'})
                return
            
            # 验证 Gateway token
            if not self._verify_gateway_token(gateway_token):
                self._send_json_response(401, {'error': 'Invalid token', 'message': 'Token 无效'})
                return
            
            # 创建 session
            client_ip = self.client_address[0]
            oc_session_token = session_manager.create_session(gateway_token, client_ip)
            
            self.log_message("用户登录成功: IP=%s", client_ip)
            
            self._send_json_response(200, {
                'success': True,
                'token': oc_session_token,
                'expires_in': 3600 * 24  # 24小时
            })
            
        except json.JSONDecodeError:
            self._send_json_response(400, {'error': 'Invalid JSON', 'message': '请求格式错误'})
        except Exception as e:
            self.log_message("登录错误: %s", str(e))
            self._send_json_response(500, {'error': str(e), 'message': '服务器错误'})
    
    def _handle_command(self, content_length):
        """处理快捷命令"""
        try:
            content = self.rfile.read(content_length)
            data = json.loads(content.decode('utf-8'))
            command = data.get('command')
            
            if not command:
                self._send_json_response(400, {'error': 'Command required', 'message': '请提供命令'})
                return
            
            # 获取 gateway token
            gateway_token = getattr(self, 'gateway_token', None)
            if not gateway_token:
                self._send_json_response(401, {'error': 'Not authenticated', 'message': '未认证'})
                return
            
            # 发送命令到 Gateway
            result = self._send_gateway_command(gateway_token, command)
            
            self._send_json_response(200, {
                'success': True,
                'result': result
            })
            
        except json.JSONDecodeError:
            self._send_json_response(400, {'error': 'Invalid JSON', 'message': '请求格式错误'})
        except Exception as e:
            self.log_message("命令执行错误: %s", str(e))
            self._send_json_response(500, {'error': str(e), 'message': '命令执行失败'})
    
    def _handle_sessions_list(self):
        """处理 Sessions 列表请求 - 从本地文件获取最近24小时的会话"""
        try:
            # 验证登录 - 支持三种方式：
            # 1. 从已登录的 session 获取 gateway_token（已通过 _check_auth 验证）
            # 2. 从请求头 X-Gateway-Token 直接获取
            # 3. 从 Authorization: Bearer oc_session_token 获取（由 _check_auth 设置）
            
            # 如果 gateway_token 已经通过 _check_auth 设置，直接使用
            gateway_token = getattr(self, 'gateway_token', None)
            
            # 如果没有 gateway_token，尝试从 oc_session_token 获取
            if not gateway_token:
                auth_header = self.headers.get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    oc_session_token = auth_header[7:]
                    client_ip = self.client_address[0]
                    if oc_session_token and session_manager.verify_session(oc_session_token, client_ip):
                        gateway_token = session_manager.get_gateway_token(oc_session_token)
                        self.log_message("[Sessions] 从 oc_session_token 获取 gateway_token 成功")
            
            # 如果还是没有，尝试从 X-Gateway-Token 获取
            if not gateway_token:
                gateway_token = self.headers.get('X-Gateway-Token', '')
            
            self.log_message("[Sessions] gateway_token present: %s, value: %s", bool(gateway_token), str(gateway_token)[:10]+'...' if gateway_token else 'N/A')
            
            if not gateway_token:
                self._send_json_response(401, {'error': 'Not authenticated', 'message': '未认证'})
                return
            
            # 调用 Gateway API 验证 token
            if not self._verify_gateway_token(gateway_token):
                self._send_json_response(401, {'error': 'Invalid token', 'message': 'Token 无效'})
                return
            
            # 直接从文件系统读取 sessions.json 文件
            self.log_message("[Sessions] 开始读取 sessions, agents_dir=%s", agents_dir if 'agents_dir' in locals() else os.path.join(os.path.dirname(WORKSPACE_DIR), 'agents'))
            agents_dir = os.path.join(os.path.dirname(WORKSPACE_DIR), 'agents')
            self.log_message("[Sessions] agents_dir exists=%s", os.path.exists(agents_dir))
            all_sessions = []
            now_ms = int(time.time() * 1000)
            cutoff_ms = now_ms - (24 * 60 * 60 * 1000)  # 24小时前
            
            # 遍历所有 agent 目录
            if os.path.exists(agents_dir):
                for agent_id in os.listdir(agents_dir):
                    sessions_file = os.path.join(agents_dir, agent_id, 'sessions', 'sessions.json')
                    if os.path.exists(sessions_file):
                        try:
                            with open(sessions_file, 'r', encoding='utf-8') as f:
                                sessions_data = json.load(f)
                            
                            for session_key, session_info in sessions_data.items():
                                updated_at = session_info.get('updatedAt', 0)
                                
                                # 只保留24小时内的会话
                                if updated_at >= cutoff_ms:
                                    # 提取会话标题和消息预览
                                    session_title = ''
                                    last_message = ''
                                    
                                    # 1. 优先使用 label 字段（如"Cron: pr-review-auto"、"爸爸"、"妈妈"）
                                    label = session_info.get('label', '')
                                    if label:
                                        session_title = label
                                    else:
                                        # 2. 从 origin 提取标题（用户标签/渠道）
                                        origin = session_info.get('origin', {})
                                        if origin:
                                            origin_label = origin.get('label', '')
                                            if origin_label:
                                                session_title = origin_label
                                            else:
                                                # 使用 from 字段
                                                from_field = origin.get('from', '')
                                                if from_field and ':' in from_field:
                                                    session_title = from_field.split(':')[-1][:20]
                                    
                                    # 判断 kind（在生成标题之前）
                                    if ':cron:' in session_key:
                                        kind = 'cron'
                                    elif ':feishu:' in session_key:
                                        kind = 'feishu'
                                    elif ':openai:' in session_key:
                                        kind = 'openai'
                                    elif ':xiao' in session_key and 'voice' in session_key:
                                        kind = 'voice'
                                    elif session_key == 'agent:main:main':
                                        kind = 'main'
                                    else:
                                        kind = 'other'
                                    
                                    # 3. 如果还是没有标题，根据 kind 生成
                                    if not session_title:
                                        if session_key == 'agent:main:main':
                                            session_title = '🏠 主会话'
                                        elif ':xiao' in session_key and 'voice' in session_key:
                                            session_title = '🎤 语音助手'
                                        elif kind == 'cron':
                                            session_title = '⏰ 定时任务'
                                        elif kind == 'feishu':
                                            session_title = '📱 飞书消息'
                                        elif kind == 'openai':
                                            session_title = '🤖 OpenAI'
                                        else:
                                            # 从 sessionKey 提取有意义的名称
                                            if 'voice' in session_key.lower():
                                                session_title = '🎤 语音会话'
                                            else:
                                                session_title = '💬 会话'
                                    
                                    # 2. 从 sessionFile 读取最新消息
                                    session_file = session_info.get('sessionFile', '')
                                    if session_file and os.path.exists(session_file):
                                        try:
                                            with open(session_file, 'r', encoding='utf-8') as f:
                                                lines = f.readlines()
                                                if lines:
                                                    last_line = json.loads(lines[-1].strip())
                                                    if isinstance(last_line, dict):
                                                        content = last_line.get('content', '') or last_line.get('text', '')
                                                        if isinstance(content, str) and content:
                                                            last_message = content[:50]
                                                        elif isinstance(content, list):
                                                            for c in content:
                                                                if isinstance(c, dict) and c.get('type') == 'text':
                                                                    last_message = c.get('text', '')[:50]
                                                                    break
                                        except Exception as e:
                                            self.log_message("读取 session 文件失败 %s: %s", session_file, str(e))
                                    
                                    # 如果没有消息，显示默认文本
                                    if not last_message:
                                        last_message = '(无消息)' 
                                    
                                    all_sessions.append({
                                        'sessionKey': session_key,
                                        'updatedAt': updated_at,
                                        'model': session_info.get('model', ''),
                                        'kind': kind,
                                        'lastMessage': last_message,
                                        'sessionTitle': session_title,
                                        'isMain': session_key == 'agent:main:main',
                                        'agentId': agent_id
                                    })
                        except Exception as e:
                            self.log_message("读取 sessions 文件失败 %s: %s", sessions_file, str(e))
            
            # 按更新时间排序（最新的在前）
            all_sessions.sort(key=lambda x: x.get('updatedAt', 0), reverse=True)
            
            self._send_json_response(200, {
                'success': True,
                'sessions': all_sessions
            })
            
        except Exception as e:
            self.log_message("Sessions 列表错误: %s", str(e))
            self._send_json_response(500, {'error': str(e), 'message': '获取会话列表失败'})
    
    def _send_gateway_command(self, gateway_token, command):
        """发送命令到 Gateway"""
        try:
            # 命令映射到 Gateway API
            command_map = {
                '/status': 'session.status',
                '/compact': 'session.compact',
                '/context detail': 'session.context',
                '/stop': 'session.stop',
                '/new': 'session.new',
                '/help': 'session.help',
            }
            
            method = command_map.get(command)
            if not method:
                return {'error': f'未知命令: {command}'}
            
            req = urllib.request.Request(
                f"{GATEWAY_HTTP}/api/rpc",
                data=json.dumps({
                    'method': method,
                    'params': {}
                }).encode('utf-8'),
                headers={
                    'Authorization': f'Bearer {gateway_token}',
                    'Content-Type': 'application/json'
                },
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode('utf-8'))
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            self.log_message("Gateway HTTP 错误: %d %s", e.code, error_body)
            return {'error': f'Gateway 错误: {e.code}'}
        except Exception as e:
            self.log_message("Gateway 请求错误: %s", str(e))
            return {'error': f'Gateway 请求失败: {str(e)}'}
    
    def _handle_models(self):
        """处理模型列表请求 - 从 Gateway 配置动态获取"""
        try:
            # 根据 WORKSPACE_DIR 推断配置文件路径
            # WORKSPACE_DIR = /home/user/.openclaw/workspace
            # 配置文件 = /home/user/.openclaw/openclaw.json
            openclaw_dir = os.path.dirname(WORKSPACE_DIR)
            config_path = os.path.join(openclaw_dir, 'openclaw.json')
            
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"配置文件不存在: {config_path}")
            
            models = []
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            providers = config.get('models', {}).get('providers', {})
            for provider_name, provider_data in providers.items():
                for model in provider_data.get('models', []):
                    model_id = model.get('id', '')
                    model_name = model.get('name', model_id)
                    full_id = f"{provider_name}/{model_id}"
                    # 在名称前添加 provider 前缀，便于区分
                    display_name = f"{model_name} ({provider_name})"
                    models.append({
                        'id': full_id,
                        'name': display_name,
                        'provider': provider_name
                    })
            
            # 不返回 current，让前端完全依赖 localStorage
            # 清理 localStorage 后，模型选择会重置为默认行为
            self._send_json_response(200, {
                'models': models
            })
        except Exception as e:
            self.log_message("读取模型列表失败：%s", str(e))
            # 失败时返回默认列表
            self._send_json_response(200, {
                'models': [
                    {'id': 'bailian/glm-5', 'name': 'GLM-5', 'provider': 'bailian'},
                    {'id': 'bailian/kimi-k2.5', 'name': 'Kimi K2.5', 'provider': 'bailian'},
                    {'id': 'bailian/qwen3.5-plus', 'name': 'Qwen 3.5 Plus', 'provider': 'bailian'}
                ]
            })
    
    def _handle_model_switch(self, content_length):
        """处理模型切换请求"""
        try:
            body = self.rfile.read(content_length)
            data = json.loads(body)
            model_id = data.get('model')
            
            if not model_id:
                self._send_json_response(400, {'error': 'Missing model parameter'})
                return
            
            # 代理到 Gateway
            req = urllib.request.Request(
                GATEWAY_HTTP + '/api/model',
                data=json.dumps({'model': model_id}).encode(),
                method='POST'
            )
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                resp_data = json.loads(response.read().decode())
                self._send_json_response(200, resp_data)
        except Exception as e:
            self.log_message("Model switch error: %s", str(e))
            self._send_json_response(500, {'error': str(e)})
    
    def _handle_config(self):
        """处理配置请求（返回默认配置）"""
        import socket
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
        except:
            local_ip = 'localhost'
        
        ws_host = os.environ.get('WS_HOST', local_ip)
        ws_port = os.environ.get('WS_PORT', '18789')
        default_ws_url = f'ws://{ws_host}:{ws_port}/'
        
        self._send_json_response(200, {
            'defaults': {
                'wsUrl': default_ws_url,
                'sessionKey': 'agent:main:main',
            },
            'info': {
                'hostname': hostname,
                'local_ip': local_ip,
                'ws_port': ws_port,
            }
        })
    
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Openclaw-Session-Key")
        self.end_headers()
    
    def end_headers(self):
        """添加通用响应头"""
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """多线程 TCP 服务器"""
    allow_reuse_address = True
    daemon_threads = True
    
    def __init__(self, *args, **kwargs):
        socketserver.TCPServer.__init__(self, *args, **kwargs)
        self.socket.settimeout(1.0)


def main():
    # 安全检查：禁止绑定 0.0.0.0
    if BIND_HOST == "0.0.0.0":
        print("""
╔════════════════════════════════════════════════════════════════╗
║                    ⛔ 安全错误：BIND_HOST = '0.0.0.0'           ║
╚════════════════════════════════════════════════════════════════╝

🚨 拒绝启动！BIND_HOST = '0.0.0.0' 会使服务暴露到公网！

⚠️  这会带来严重的安全风险：
   • 任何人都可以访问你的 AI 助手
   • 你的数据可能被窃取
   • 攻击者可能利用你的服务

✅ 请修改 server_config.py 中的 BIND_HOST：
   
   推荐配置：
   ─────────────────────────────────────────────────────────────
   │ BIND_HOST = '127.0.0.1'    # 仅本机访问（最安全，默认）
   │ BIND_HOST = '100.x.x.x'    # Tailscale IP（VPN 访问，安全）
   │ BIND_HOST = '192.168.x.x'  # 内网 IP（局域网访问）
   ─────────────────────────────────────────────────────────────

💡 如需远程访问，请使用 Tailscale 等 VPN 方案：
   1. 安装 Tailscale: curl -fsSL https://tailscale.com/install.sh | sh
   2. 获取 Tailscale IP: tailscale ip
   3. 重新运行 setup.py 配置

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
服务已拒绝启动，请修改配置后重试。
""")
        sys.exit(1)
    
    os.chdir(WORKSPACE_DIR)
    
    print(f"Starting OpenClaw Web Server on port {PORT}...")
    print(f"")
    print(f"🔒 安全配置:")
    print(f"   BIND_HOST = {BIND_HOST}")
    if BIND_HOST == "127.0.0.1":
        print(f"   ✅ 仅本机可访问（最安全）")
    elif BIND_HOST.startswith("100."):
        print(f"   ✅ 仅 Tailscale VPN 可访问（安全）")
    elif BIND_HOST.startswith("192.168.") or BIND_HOST.startswith("10."):
        print(f"   ⚠️  局域网可访问")
    print(f"")
    print(f"📁 目录配置:")
    print(f"   Workspace: {WORKSPACE_DIR}")
    print(f"   Dashboard: {DASHBOARD_DIR}")
    print(f"   Media:     {MEDIA_DIR}")
    print(f"   Gateway:   {GATEWAY_HTTP}")
    print(f"")
    
    print(f"🌐 访问地址:")
    print(f"   Dashboard:   http://{TAILSCALE_DOMAIN}:{PORT}/")
    print(f"   Mobile:      http://{TAILSCALE_DOMAIN}:{PORT}/mobile.html")
    print(f"   Browse:      http://{TAILSCALE_DOMAIN}:{PORT}/browse/")
    print(f"   Media files: http://{TAILSCALE_DOMAIN}:{PORT}/media/")
    
    with ThreadedTCPServer((BIND_HOST, PORT), ProxyServer) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
            httpd.shutdown()


if __name__ == "__main__":
    import socket
    main()
