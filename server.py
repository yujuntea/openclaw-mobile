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
import json
import os
import sys
import uuid
import base64
import time
import re
import html as html_module

# 添加配置文件搜索路径
_config_paths = [
    os.path.dirname(os.path.realpath(__file__)),  # 脚本所在目录
    os.path.dirname(os.path.realpath(__file__)),  # workspace 目录（如果是符号链接）
    '/root/.openclaw/workspace',  # 默认 workspace 目录
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
    print(f"[Config] Loaded from server_config.py: BIND_HOST={BIND_HOST}")
except ImportError as e:
    print(f"[Config] server_config.py not found, using defaults: {e}")
    # 如果没有配置文件，使用默认值
    PORT = 8080
    BIND_HOST = '0.0.0.0'  # 监听所有接口
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
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {self.address_string()} - {format % args}")
    
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
        # API 代理
        if self.path.startswith('/api/'):
            self._handle_get_proxy()
            return
        
        # Mobile 页面（默认）
        if self.path == '/' or self.path == '/index.html':
            # 直接使用 SimpleHTTPRequestHandler 的方式
            self.path = '/mobile.html'
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        
        if self.path.startswith('/assets/'):
            self._serve_dashboard_file(self.path[1:])
            return
        
        if self.path in ['/favicon.svg', '/favicon-32.png', '/favicon.ico', '/apple-touch-icon.png']:
            self._serve_dashboard_file(self.path[1:])
            return
        
        # Media 文件服务
        if self.path.startswith('/media/'):
            self._serve_media_file(self.path[7:])
            return
        
        # 目录浏览
        if self.path.startswith('/browse/'):
            self._serve_directory_listing(self.path[8:])
            return
        
        # 其他静态文件（mobile.html 等）
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):
        """处理 POST 请求"""
        content_length = int(self.headers.get('Content-Length', 0))
        
        # 检查请求大小
        if content_length > MAX_REQUEST_SIZE:
            self.send_error(413, "Request too large")
            return
        
        # 图片上传 API
        if self.path == '/api/upload':
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
            
            # 图片预览
            preview = ''
            if not item['is_dir'] and item['name'].lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                img_path = f"/media/{sub_path}/{item['name']}" if sub_path else f"/media/{item['name']}"
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
                '.txt': 'text/plain', '.md': 'text/markdown',
                '.json': 'application/json', '.xml': 'application/xml',
                '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
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
        """处理图片上传"""
        try:
            content_type = self.headers.get('Content-Type', '')
            
            if 'multipart/form-data' in content_type:
                # Multipart 上传
                body = self.rfile.read(content_length)
                match = re.search(b'data:image/([^;]+);base64,([A-Za-z0-9+/=]+)', body)
                if match:
                    img_data = base64.b64decode(match.group(2))
                    ext = match.group(1).decode()
                else:
                    self._send_json_response(400, {"error": "No image data found"})
                    return
            else:
                # JSON 格式上传
                body = self.rfile.read(content_length)
                data = json.loads(body)
                
                img_data = None
                ext = 'jpg'
                
                if 'image' in data:
                    img_base64 = data['image']
                    if ',' in img_base64:
                        img_base64 = img_base64.split(',')[1]
                    img_data = base64.b64decode(img_base64)
                
                if not img_data:
                    self._send_json_response(400, {"error": "No image data"})
                    return
            
            # 保存到 inbound 目录
            filename = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join(INBOUND_DIR, filename)
            
            os.makedirs(INBOUND_DIR, exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(img_data)
            
            self._send_json_response(200, {
                "success": True,
                "path": filepath,
                "filename": filename
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
    os.chdir(WORKSPACE_DIR)
    
    print(f"Starting OpenClaw Web Server on port {PORT}...")
    print(f"Workspace: {WORKSPACE_DIR}")
    print(f"Dashboard: {DASHBOARD_DIR}")
    print(f"Media: {MEDIA_DIR}")
    print(f"Gateway: {GATEWAY_HTTP}")
    print(f"")
    
    print(f"Access URLs:")
    print(f"  - Dashboard:   http://{TAILSCALE_DOMAIN}:{PORT}/")
    print(f"  - Mobile:      http://{TAILSCALE_DOMAIN}:{PORT}/mobile.html")
    print(f"  - Browse:      http://{TAILSCALE_DOMAIN}:{PORT}/browse/")
    print(f"  - Media files: http://{TAILSCALE_DOMAIN}:{PORT}/media/")
    
    with ThreadedTCPServer((BIND_HOST, PORT), ProxyServer) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
            httpd.shutdown()


if __name__ == "__main__":
    import socket
    main()
