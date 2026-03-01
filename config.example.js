/**
 * OpenClaw Mobile 配置文件
 * 
 * 使用方法：
 * 1. 复制此文件为 config.js
 * 2. 修改下面的配置值
 * 3. 在 mobile.html 中引入：<script src="config.js"></script>
 */

const OPENCLAW_CONFIG = {
  // ===========================================
  // 应用配置
  // ===========================================
  app: {
    // 应用名称（显示在页面顶部）
    appName: '小强 AI',
    appNameEn: 'XiaoQiang AI',
    
    // 应用描述
    appDesc: 'AI 家庭助手',
    appDescEn: 'AI Family Assistant',
  },
  
  // ===========================================
  // Gateway 配置
  // ===========================================
  gateway: {
    // 默认 WebSocket 地址
    // 本地开发: ws://localhost:18789/
    // Tailscale: ws://your-host.tailXXXX.ts.net:18789/
    // HTTPS: wss://your-domain.com/
    defaultWsUrl: 'ws://localhost:18789/',
    
    // 默认 Token（从 Gateway 获取）
    // 获取方法: cat ~/.openclaw/openclaw.json | jq -r '.gateway.auth.token'
    defaultToken: 'YOUR_GATEWAY_TOKEN_HERE',
    
    // 默认会话 Key
    defaultSessionKey: 'agent:main:main',
    
    // 代理地址（通常不需要修改）
    proxyUrl: '/api'
  },

  // ===========================================
  // 云端口转发配置（可选）
  // ===========================================
  cloudForward: {
    // 是否启用云端口转发检测
    enabled: true,
    
    // 云服务商域名检测
    // 如果访问域名匹配此模式，自动使用云端口转发的 WebSocket 地址
    domainPattern: '.your-cloud-provider.example.com',
    
    // 云端口转发的 WebSocket 地址（WSS）
    // 示例：'wss://your-wss-domain.orcaterm.cloud.tencent.com/'
    wsUrl: 'wss://your-wss-domain.example.com/'
  },

  // ===========================================
  // Tailscale 配置（可选）
  // ===========================================
  tailscale: {
    // 是否启用 Tailscale 域名检测
    enabled: true,
    
    // Tailscale 域名模式
    domainPattern: '.tailXXXX.ts.net',
    
    // WebSocket 端口
    wsPort: 18789
  },

  // ===========================================
  // UI 配置
  // ===========================================
  ui: {
    // 登录状态有效期（毫秒）
    // 默认 1 小时
    loginExpiryMs: 60 * 60 * 1000,
    
    // 历史消息最大数量
    maxHistory: 100,
    
    // Dashboard 链接（导航菜单）
    dashboardUrl: 'http://localhost:18789/',
    
    // 文件浏览链接
    browseUrl: '/browse/',
    
    // Media 文件链接
    mediaUrl: '/media/'
  },

  // ===========================================
  // 调试配置
  // ===========================================
  debug: {
    // 是否启用调试日志
    enableConsoleLog: true,
    
    // 是否显示详细错误信息
    showDetailedErrors: false
  }
};

// ===========================================
// 辅助函数
// ===========================================

/**
 * 获取 WebSocket URL（自动检测环境）
 */
function getWebSocketUrl() {
  const currentHost = window.location.hostname;
  const currentProtocol = window.location.protocol;
  
  // 云端口转发检测
  if (OPENCLAW_CONFIG.cloudForward.enabled && 
      currentHost.includes(OPENCLAW_CONFIG.cloudForward.domainPattern)) {
    // 优先使用云端口转发的 wsUrl
    if (OPENCLAW_CONFIG.cloudForward.wsUrl) {
      return OPENCLAW_CONFIG.cloudForward.wsUrl;
    }
    // 没有配置时，使用 wss://当前域名/
    return `wss://${currentHost}/`;
  }
  
  // Tailscale 检测
  if (OPENCLAW_CONFIG.tailscale.enabled && 
      currentHost.includes(OPENCLAW_CONFIG.tailscale.domainPattern)) {
    return `ws://${currentHost}:${OPENCLAW_CONFIG.tailscale.wsPort}/`;
  }
  
  // 默认
  return OPENCLAW_CONFIG.gateway.defaultWsUrl;
}

/**
 * 获取 Token
 */
function getToken() {
  // 优先从 localStorage 读取
  const savedToken = localStorage.getItem('oc_token');
  if (savedToken && savedToken !== 'YOUR_GATEWAY_TOKEN_HERE') {
    return savedToken;
  }
  
  // 使用配置中的默认值
  return OPENCLAW_CONFIG.gateway.defaultToken;
}

// 导出到全局（供 mobile.html 使用）
if (typeof window !== 'undefined') {
  window.OPENCLAW_CONFIG = OPENCLAW_CONFIG;
  window.getWebSocketUrl = getWebSocketUrl;
  window.getToken = getToken;
}

// 导出（如果使用模块系统）
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { OPENCLAW_CONFIG, getWebSocketUrl, getToken };
}
