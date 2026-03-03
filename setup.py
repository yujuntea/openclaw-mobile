#!/usr/bin/env python3
"""
OpenClaw Mobile 一键配置工具

功能：
1. 自动检测环境信息（Tailscale IP、Gateway token）
2. 交互式配置
3. 自动生成配置文件
4. 自动配置 systemd 服务
5. 自动更新 Gateway allowedOrigins

使用方法：
    python3 setup.py
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

# 颜色定义
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_step(msg):
    print(f"\n{BLUE}📋 {msg}{RESET}")

def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def print_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def input_default(prompt, default=""):
    """带默认值的输入"""
    if default:
        return input(f"{prompt} [{default}]: ").strip() or default
    return input(f"{prompt}: ").strip()

def get_gateway_token():
    """自动获取 Gateway token"""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
                token = config.get("gateway", {}).get("auth", {}).get("token")
                if token:
                    return token
        except:
            pass
    return None

def get_tailscale_ip():
    """自动获取 Tailscale IP"""
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return None

def get_tailscale_hostname():
    """自动获取 Tailscale 完整域名"""
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # 查找当前主机（Self）
            if "Self" in data:
                self_node = data["Self"]
                dns_name = self_node.get("DNSName", "")
                if dns_name:
                    # 返回完整的 DNSName，去掉末尾的点
                    return dns_name.rstrip(".")
                # 如果没有 DNSName，至少返回 HostName
                hostname = self_node.get("HostName")
                if hostname:
                    return hostname
    except:
        pass
    return None

def get_gateway_port():
    """从 Gateway 配置读取端口"""
    default_port = 18789
    try:
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                return config.get("gateway", {}).get("port", default_port)
    except:
        pass
    return default_port

def get_dashboard_port():
    """从 server_config.py 读取端口"""
    default_port = 8080
    try:
        config_path = Path.cwd().parent / "server_config.py"
        if config_path.exists():
            with open(config_path) as f:
                content = f.read()
                import re
                match = re.search(r'PORT\s*=\s*(\d+)', content)
                if match:
                    return int(match.group(1))
    except:
        pass
    return default_port

def detect_environment():
    """自动检测环境信息"""
    env = {}
    
    # 获取 Gateway token
    print_step("检测环境信息...")
    token = get_gateway_token()
    if token:
        env["gateway_token"] = token
        print_success(f"自动检测到 Gateway Token: {token[:20]}...")
    else:
        print_warning("无法自动获取 Gateway Token，请手动输入")
    
    # 获取 Tailscale IP
    ts_ip = get_tailscale_ip()
    if ts_ip:
        env["tailscale_ip"] = ts_ip
        print_success(f"自动检测到 Tailscale IP: {ts_ip}")
    
    # 获取 Tailscale 主机名
    ts_host = get_tailscale_hostname()
    if ts_host:
        env["tailscale_hostname"] = ts_host
        print_success(f"自动检测到 Tailscale 主机名: {ts_host}")
    
    # 检查 systemd
    env["has_systemd"] = shutil.which("systemctl") is not None
    
    return env

def backup_existing_configs():
    """备份已存在的配置文件"""
    import shutil
    from datetime import datetime
    
    # 使用 setup.py 所在目录的父目录作为基准路径（确保路径一致性）
    base_dir = Path(__file__).parent.parent
    backup_dir = base_dir / "config-backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    config_files = [
        (base_dir / "config.js", "config.js"),
        (base_dir / "server_config.py", "server_config.py"),
        (Path.home() / ".openclaw" / "openclaw.json", "openclaw.json"),
    ]
    
    backed_up = []
    for src, name in config_files:
        if src.exists():
            dst = backup_dir / f"{name}.{timestamp}"
            shutil.copy2(src, dst)
            backed_up.append(str(dst))
            print_success(f"已备份: {name} -> {dst}")
    
    return backed_up


def update_gateway_config(hosts, cloud_host=""):
    """自动更新 Gateway 的 allowedOrigins
    
    参数:
    - hosts: 域名/IP 列表（如 ["localhost", "100.x.x.x", "vm-0-12...ts.net"]）
    - cloud_host: 云转发域名（可选）
    
    自动为每个域名/IP 添加:
    - Dashboard 端口（从 server_config.py 读取）
    - Gateway 端口（从 openclaw.json 读取）
    - http 和 https 协议
    """
    # 动态读取端口
    dashboard_port = get_dashboard_port()
    gateway_port = get_gateway_port()
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    
    if not config_path.exists():
        print_warning(f"Gateway 配置文件不存在: {config_path}")
        return False
    
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        # 获取当前 allowedOrigins
        allowed = config.get("gateway", {}).get("controlUi", {}).get("allowedOrigins", [])
        
        # 先清理现有的重复项（保留顺序）
        seen = set()
        allowed_clean = []
        for url in allowed:
            if url not in seen:
                seen.add(url)
                allowed_clean.append(url)
        allowed = allowed_clean
        
        # 自动为每个域名/IP 添加端口和协议
        new_origins = []
        for host in hosts:
            # 添加 Dashboard 端口
            http_dashboard = f"http://{host}:{dashboard_port}"
            if http_dashboard not in allowed:
                new_origins.append(http_dashboard)
            https_dashboard = f"https://{host}:{dashboard_port}"
            if https_dashboard not in allowed:
                new_origins.append(https_dashboard)
            
            # 添加 Gateway 端口
            http_gateway = f"http://{host}:{gateway_port}"
            if http_gateway not in allowed:
                new_origins.append(http_gateway)
            https_gateway = f"https://{host}:{gateway_port}"
            if https_gateway not in allowed:
                new_origins.append(https_gateway)
        
        # 添加云转发域名的地址（腾讯云转发已在内部做端口映射，不需要添加端口号）
        if cloud_host:
            # 添加裸域名（http 和 https）
            http_cloud = f"http://{cloud_host}"
            if http_cloud not in allowed:
                new_origins.append(http_cloud)
            https_cloud = f"https://{cloud_host}"
            if https_cloud not in allowed:
                new_origins.append(https_cloud)
        
        if new_origins:
            allowed.extend(new_origins)
            # 再次去重确保无重复
            seen = set()
            allowed_final = []
            for url in allowed:
                if url not in seen:
                    seen.add(url)
                    allowed_final.append(url)
            allowed = allowed_final
            
            # 更新配置
            if "controlUi" not in config.get("gateway", {}):
                config.setdefault("gateway", {}).setdefault("controlUi", {})["allowedOrigins"] = allowed
            else:
                config["gateway"]["controlUi"]["allowedOrigins"] = allowed
            
            # 备份并保存（带时间戳，保存到统一备份目录）
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_dir = Path(__file__).parent.parent / "config-backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"openclaw.json.{timestamp}"
            shutil.copy2(config_path, backup_path)
            print_success(f"已备份: openclaw.json -> {backup_path}")
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print_success(f"已更新 Gateway 配置，新增: {new_origins}")
            
            # 提示需要重启 Gateway
            print_warning("配置已更新，需要重启 Gateway 才能生效")
            print(f"   运行: {BOLD}systemctl --user restart openclaw-gateway{RESET}")
            
            return True
        else:
            print_success("Gateway allowedOrigins 已包含所有访问地址")
            return True
            
    except Exception as e:
        print_error(f"更新 Gateway 配置失败: {e}")
        return False

def create_config_js(config, gateway_port=18789):
    """生成 config.js"""
    template = '''/**
 * OpenClaw Mobile 配置文件
 * 自动生成于 {timestamp}
 */

const OPENCLAW_CONFIG = {{
  // 应用配置
  app: {{
    appName: '{app_name}',
    appNameEn: '{app_name_en}',
    appDesc: '{app_desc}',
    appDescEn: '{app_desc_en}',
  }},
  
  // Gateway 配置
  gateway: {{
    // 默认 WebSocket 地址
    defaultWsUrl: '{ws_url_default}',
    
    // 默认 Token
    defaultToken: '{gateway_token}',
    defaultSessionKey: 'agent:main:main',
    proxyUrl: '/api'
  }},

  // 云端口转发配置
  cloudForward: {{
    enabled: {cloud_enabled},
    domainPattern: '{cloud_domain_pattern}',
    wsUrl: '{ws_url_cloud}'
  }},

  // Tailscale 配置
  tailscale: {{
    enabled: {tailscale_enabled},
    domainPattern: '{tailscale_domain_pattern}',
    wsUrl: '{ws_url_tailscale}',
    wsPort: {gateway_port}
  }},

  // UI 配置
  ui: {{
    loginExpiryMs: 60 * 60 * 1000,
    maxHistory: 100,
    dashboardUrl: '{dashboard_url}',
    browseUrl: '/browse/',
    mediaUrl: '/media/'
  }},

  // 调试配置
  debug: {{
    enableConsoleLog: true,
    showDetailedErrors: false
  }}
}};

/**
 * 获取 WebSocket URL（自动检测环境）
 */
function getWebSocketUrl() {{
  const currentHost = window.location.hostname;
  
  // 1. 云端口转发检测
  if (OPENCLAW_CONFIG.cloudForward.enabled && 
      currentHost.includes(OPENCLAW_CONFIG.cloudForward.domainPattern)) {{
    if (OPENCLAW_CONFIG.cloudForward.wsUrl) {{
      return OPENCLAW_CONFIG.cloudForward.wsUrl;
    }}
    return `wss://${{currentHost}}/`;
  }}
  
  // 2. Tailscale 检测
  if (OPENCLAW_CONFIG.tailscale.enabled && 
      currentHost.includes(OPENCLAW_CONFIG.tailscale.domainPattern)) {{
    if (OPENCLAW_CONFIG.tailscale.wsUrl) {{
      return OPENCLAW_CONFIG.tailscale.wsUrl;
    }}
    return `ws://${{currentHost}}:${{OPENCLAW_CONFIG.tailscale.wsPort}}/`;
  }}
  
  // 3. 自定义域名/其他方式
  return OPENCLAW_CONFIG.gateway.defaultWsUrl;
}}

/**
 * 获取 Token
 */
function getToken() {{
  const savedToken = localStorage.getItem('oc_token');
  if (savedToken && savedToken !== 'YOUR_GATEWAY_TOKEN_HERE') {{
    return savedToken;
  }}
  return OPENCLAW_CONFIG.gateway.defaultToken;
}}

if (typeof window !== 'undefined') {{
  window.OPENCLAW_CONFIG = OPENCLAW_CONFIG;
  window.getWebSocketUrl = getWebSocketUrl;
  window.getToken = getToken;
}}
'''
    
    from datetime import datetime
    
    # 推断域名模式
    domain = config.get("domain", "")
    cloud_http = config.get("cloud_http_domain", "")
    cloud_ws = config.get("ws_url_cloud", "")
    
    
    # 云转发域名模式
    if cloud_http:
        # 从完整域名提取模式（如 demo.orcaterm.cloud.tencent.com -> .orcaterm.cloud.tencent.com）
        if '.' in cloud_http:
            cloud_pattern = '.' + cloud_http.split('.', 1)[1]  # 去掉第一部分，取剩余部分
        else:
            cloud_pattern = cloud_http
    elif cloud_ws:
        # 从 wsUrl 提取域名
        import re
        match = re.search(r'wss?://([^/]+)', cloud_ws)
        if match:
            domain = match.group(1)
            if '.' in domain:
                cloud_pattern = '.' + domain.split('.', 1)[1]
            else:
                cloud_pattern = domain
        else:
            cloud_pattern = '.orcaterm.cloud.tencent.com'
    else:
        cloud_pattern = '.orcaterm.cloud.tencent.com'
    
    # Tailscale 域名模式（使用正则表达式精确匹配）
    import re
    if re.search(r'\.tail[a-z0-9]+\.ts\.net$', domain, re.IGNORECASE):
        # 真正的 Tailscale 域名，提取 tailXXXX.ts.net 部分
        ts_pattern = '.tail' + domain.split('.tail')[-1].split('.')[0] + '.ts.net'
    else:
        ts_pattern = '.tailXXXX.ts.net'
    
    return template.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        app_name=config.get("app_name", "小强 AI"),
        app_name_en=config.get("app_name_en", "XiaoQiang AI"),
        app_desc=config.get("app_desc", "AI 家庭助手"),
        app_desc_en=config.get("app_desc_en", "AI Family Assistant"),
        ws_url_default=config.get("ws_url_default", f"ws://localhost:{gateway_port}/"),
        ws_url_tailscale=config.get("ws_url_tailscale", f"ws://localhost:{gateway_port}/"),
        ws_url_cloud=config.get("ws_url_cloud", ""),
        gateway_token=config.get("gateway_token", "YOUR_TOKEN_HERE"),
        cloud_enabled="true" if config.get("cloud_enabled") else "false",
        cloud_domain_pattern=cloud_pattern,
        tailscale_enabled="true" if config.get("tailscale_enabled") else "false",
        tailscale_domain_pattern=ts_pattern,
        dashboard_url=config.get("dashboard_url", f"http://localhost:{gateway_port}/"),
        gateway_port=gateway_port,
    )

def create_server_config_py(config, dashboard_port=8080, gateway_port=18789):
    """生成 server_config.py"""
    from datetime import datetime
    import os
    
    dashboard_dir = config.get("dashboard_dir", "/path/to/openclaw/dist/control-ui")
    ts_ip = config.get("ts_ip", "")  # 从 config 获取 Tailscale IP
    bind_host = ts_ip if ts_ip else "0.0.0.0"  # 优先使用 Tailscale IP
    domain = config.get("domain", "your-domain.example.com")
    # 使用 setup.py 所在目录的父目录作为配置文件输出路径
    config_path = Path(__file__).parent.parent / "server_config.py"
    
    template = f'''#!/usr/bin/env python3
"""
OpenClaw Mobile Server 配置文件
自动生成于 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

警告：此文件包含敏感信息，请勿提交到 Git！
位置：{config_path}
"""

# ==========================================
# 服务器配置
# ==========================================

# 监听端口
PORT = {dashboard_port}

# 监听地址
# 优先绑定 Tailscale IP（更安全），如无则绑定所有接口
# Tailscale IP: 仅 Tailscale 网络可访问
# 0.0.0.0: 所有网络可访问（需配合防火墙）
BIND_HOST = '{bind_host}'

# 域名（用于显示访问地址）
TAILSCALE_DOMAIN = '{domain}'

# ==========================================
# Gateway 配置
# ==========================================

GATEWAY_HTTP = 'http://127.0.0.1:18789'

# ==========================================
# 目录配置
# ==========================================

import os

# 工作目录（自动检测）
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Dashboard 目录
DASHBOARD_DIR = '{dashboard_dir}'

# 媒体目录
MEDIA_DIR = os.path.join(WORKSPACE_DIR, 'media')

# 入站文件目录
INBOUND_DIR = os.path.join(MEDIA_DIR, 'inbound')

# ==========================================
# 其他配置
# ==========================================

REQUEST_TIMEOUT = 30
MAX_REQUEST_SIZE = 50 * 1024 * 1024  # 50MB

BROWSABLE_DIRS = {{
    'media': MEDIA_DIR,
    'workspace': WORKSPACE_DIR,
}}
'''
    return template

def create_systemd_service(config):
    """生成 systemd 服务文件"""
    workspace = os.path.dirname(os.path.abspath(__file__))
    
    template = f'''[Unit]
Description=OpenClaw Web Server (Dashboard + Mobile + Media)
After=network.target

[Service]
Type=simple
WorkingDirectory={workspace}
ExecStart=/usr/bin/python3 {workspace}/server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
'''
    return template

def main():
    print(f"""
{BOLD}╔═══════════════════════════════════════════╗
║     OpenClaw Mobile 一键配置工具          ║
╚═══════════════════════════════════════════╝{RESET}
""")
    
    # 自动检测环境
    env = detect_environment()
    
    # 获取端口配置
    dashboard_port = get_dashboard_port()
    gateway_port = get_gateway_port()
    print_success(f"Dashboard 端口: {dashboard_port}")
    print_success(f"Gateway 端口: {gateway_port}")
    
    print(f"""
{BOLD}📝 请确认以下配置信息:{RESET}
""")
    
    # 1. Tailscale 信息（自动检测，可修改）
    # 1. AI 助手名称配置
    print_step("AI 助手名称配置")
    app_name = input_default("助手名称（中文）", "小强 AI")
    app_name_en = input_default("助手名称（英文）", "XiaoQiang AI")
    app_desc = input_default("助手描述（中文）", "AI 家庭助手")
    app_desc_en = input_default("助手描述（英文）", "AI Family Assistant")
    
    print_step("Tailscale 配置")
    # 有检测值时：显示为默认值，回车使用；无检测值时：显示跳过
    ts_ip_default = env.get("tailscale_ip", "")
    ts_hostname_default = env.get("tailscale_hostname", "")
    
    # Tailscale IP：输入 "-" 强制跳过，不使用任何默认值
    if ts_ip_default:
        ts_ip_input = input(f"Tailscale IP [{ts_ip_default}](输入 - 跳过): ").strip()
        if ts_ip_input == "-":
            ts_ip = ""  # 强制跳过
        else:
            ts_ip = ts_ip_input if ts_ip_input else ts_ip_default  # 回车使用检测值
    else:
        ts_ip_input = input("Tailscale IP [直接回车跳过](输入 - 跳过): ").strip()
        ts_ip = "" if ts_ip_input == "-" else ts_ip_input  # 回车跳过
    
    # Tailscale 主机名：输入 "-" 强制跳过
    if ts_hostname_default:
        ts_hostname_input = input(f"Tailscale 主机名 [{ts_hostname_default}](输入 - 跳过): ").strip()
        if ts_hostname_input == "-":
            ts_hostname = ""  # 强制跳过
        else:
            ts_hostname = ts_hostname_input if ts_hostname_input else ts_hostname_default  # 回车使用检测值
    else:
        ts_hostname_input = input("Tailscale 主机名 [直接回车跳过](输入 - 跳过): ").strip()
        ts_hostname = "" if ts_hostname_input == "-" else ts_hostname_input  # 回车跳过
    
    # 2. 域名配置（用于显示和访问）
    print_step("访问域名配置")
    if ts_hostname:
        # 如果已经是完整域名（包含 .tail），直接使用；否则添加 .tailXXXX.ts.net
        if ".tail" in ts_hostname.lower():
            default_domain = ts_hostname
        else:
            default_domain = f"{ts_hostname}.tailXXXX.ts.net"
    else:
        default_domain = ""
    domain = input(f"访问域名（用于显示） [直接回车跳过]: ").strip()
    if not domain:
        domain = default_domain
    
    # 3. 云转发配置（可选）
    print_step("云端口转发配置（可选）")
    print("  直接回车跳过")
    cloud_http_domain = input("  云转发 HTTP 访问域名（如 demo.orcaterm.cloud.tencent.com）: ").strip()
    cloud_ws_url = input("  云转发 WSS 地址（如 wss://wss-demo.orcaterm.cloud.tencent.com/）: ").strip()
    
    # 4. Gateway Token
    print_step("Gateway 配置")
    gateway_token = input_default(
        "Gateway Token", 
        env.get("gateway_token", "")
    )
    
    if not gateway_token:
        print_error("Gateway Token 不能为空！")
        print(f"   获取方法: cat ~/.openclaw/openclaw.json | jq -r '.gateway.auth.token'")
        return
    
    # 5. Dashboard 目录
    print_step("目录配置")
    # 尝试自动检测 OpenClaw 安装路径
    default_dashboard = ""
    common_paths = [
        "/usr/local/lib/node_modules/openclaw/dist/control-ui",
        "/usr/lib/node_modules/openclaw/dist/control-ui",
        os.path.expanduser("~/.nvm/versions/node/v22.22.0/lib/node_modules/openclaw/dist/control-ui"),
        os.path.expanduser("~/openclaw/dist/control-ui"),
    ]
    for path in common_paths:
        if os.path.exists(path):
            default_dashboard = path
            break
    if not default_dashboard:
        default_dashboard = "/path/to/openclaw/dist/control-ui"
    
    dashboard_dir = input_default(
        "Dashboard 目录",
        default_dashboard
    )
    
    # 收集配置
    config = {
        "app_name": app_name,
        "app_name_en": app_name_en,
        "app_desc": app_desc,
        "app_desc_en": app_desc_en,
        
        # 网络配置
        "ts_ip": ts_ip,  # Tailscale IP
        "domain": domain,
        
        # 云转发配置
        "cloud_http_domain": cloud_http_domain,
        "cloud_ws_url": cloud_ws_url if cloud_ws_url else "",
        
        # WebSocket 配置
        "ws_url_tailscale": f"ws://{ts_ip}:{gateway_port}/" if ts_ip else f"ws://localhost:{gateway_port}/",
        "ws_url_cloud": cloud_ws_url if cloud_ws_url else "",
        "ws_url_default": f"ws://{domain}:{gateway_port}/" if domain else f"ws://localhost:{gateway_port}/",
        
        # 功能开关
        "tailscale_enabled": bool(ts_ip),
        "cloud_enabled": bool(cloud_http_domain or cloud_ws_url),
        
        # Token
        "gateway_token": gateway_token,
        
        # 目录
        "dashboard_dir": dashboard_dir,
        "dashboard_url": f"http://{domain}:{gateway_port}/" if domain else f"http://localhost:{gateway_port}/",
    }
    
    # 生成访问地址列表
    access_urls = [
        f"http://localhost:{dashboard_port}",
    ]
    if ts_ip:
        access_urls.extend([
            f"http://{ts_ip}:{dashboard_port}",
        ])
    if domain:
        access_urls.extend([
            f"http://{domain}:{dashboard_port}",
            f"http://{domain}",
        ])
    if cloud_http_domain:
        access_urls.extend([
            f"http://{cloud_http_domain}",
            f"http://{cloud_http_domain}:{dashboard_port}",
        ])
    
    # 开始生成配置
    # 备份现有配置文件
    print_step("备份现有配置...")
    backed_up = backup_existing_configs()
    if backed_up:
        print_success(f"已备份：{', '.join([Path(f).name for f in backed_up])}")
    else:
        print_warning("未发现现有配置文件，跳过备份")
    
    print_step("生成配置文件...")
    
    # 1. config.js
    config_js = create_config_js(config, gateway_port)
    config_js_path = Path(__file__).parent.parent / "config.js"
    with open(config_js_path, 'w') as f:
        f.write(config_js)
    print_success(f"已生成: {config_js_path}")
    
    # 2. server_config.py
    server_config_py = create_server_config_py(config, dashboard_port, gateway_port)
    server_config_py_path = Path(__file__).parent.parent / "server_config.py"
    with open(server_config_py_path, 'w') as f:
        f.write(server_config_py)
    print_success(f"已生成: {server_config_py_path}")
    
    # 3. 更新 Gateway 配置
    print_step("更新 Gateway 配置...")
    # 准备域名列表（去重）
    hosts = ["localhost"]
    if ts_ip:
        hosts.append(ts_ip)
    if ts_hostname:
        hosts.append(ts_hostname)
    if domain and domain != ts_hostname:  # 避免重复添加
        hosts.append(domain)
    
    # 去重（保持顺序）
    seen = set()
    hosts_unique = []
    for h in hosts:
        if h not in seen:
            seen.add(h)
            hosts_unique.append(h)
    hosts = hosts_unique
    
    # 提取云转发域名
    cloud_host = ""
    if cloud_http_domain:
        cloud_host = cloud_http_domain.replace("http://", "").replace("https://", "").split(":")[0]
    
    update_gateway_config(hosts, cloud_host)
    
    # 4. 创建 systemd 服务（可选）
    if env.get("has_systemd"):
        print_step("配置 Systemd 服务...")
        systemd_service = create_systemd_service(config)
        service_path = Path.home() / ".config" / "systemd" / "user" / "openclaw-web.service"
        service_path.parent.mkdir(parents=True, exist_ok=True)
        with open(service_path, 'w') as f:
            f.write(systemd_service)
        print_success(f"已生成: {service_path}")
        
        # 询问是否立即启动
        if input_default("\n是否立即启动服务？(y/n)", "y") == "y":
            subprocess.run(["systemctl", "--user", "daemon-reload"])
            subprocess.run(["systemctl", "--user", "start", "openclaw-web"])
            subprocess.run(["systemctl", "--user", "enable", "openclaw-web"])
            print_success("服务已启动并开机自启")
    else:
        print_warning("未检测到 systemd，跳过服务配置")
    
    # 完成
    print(f"""
{BOLD}╔═══════════════════════════════════════════╗
║           配置完成！                      ║
╚═══════════════════════════════════════════╝{RESET}

📱 访问地址：
   - http://localhost:{dashboard_port}/
{f"   - http://{ts_ip}:{dashboard_port}/" if ts_ip else ""}
{f"   - http://{domain}:{dashboard_port}/" if domain else ""}
{f"   - http://{cloud_http_domain}:{dashboard_port}/" if cloud_http_domain else ""}

🔧 启用功能：
   - Tailscale 访问: {"✅" if ts_ip else "❌"}
   - 云端口转发: {"✅" if (cloud_http_domain or cloud_ws_url) else "❌"}

📖 更多信息请查看 README.md
""")

if __name__ == "__main__":
    main()
