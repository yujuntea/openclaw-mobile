/**
 * OpenClaw Mobile 国际化配置
 * 
 * 支持语言：中文（zh-CN）、英文（en-US）
 * 默认语言：中文
 */

const i18n = {
  // 当前语言
  currentLang: 'zh-CN',
  
  // 语言配置
  languages: {
    'zh-CN': {
      // 通用
      appName: '小强 AI',
      appDesc: 'AI 家庭助手',
      
      // 登录页
      wsUrlPlaceholder: 'WebSocket地址',
      proxyUrlPlaceholder: '代理地址',
      tokenPlaceholder: '访问令牌',
      sessionPlaceholder: '会话ID',
      connectBtn: '连接',
      connecting: '连接中...',
      connectFailed: '连接失败',
      
      // 头部
      sessionLabel: '会话',
      refreshBtn: '刷新消息',
      menuBtn: '菜单',
      
      // 工作状态
      working: '工作中...',
      
      // 输入框
      msgPlaceholder: '发送消息...',
      sendImageBtn: '发送图片',
      removeImageBtn: '移除图片',
      previewAlt: '预览',
      
      // 菜单
      menuTitle: '📋 菜单',
      chatSection: '聊天',
      sessionList: '会话列表',
      sessionListDesc: '最近24小时的会话',
      currentSession: '当前会话',
      fileSection: '文件浏览',
      rootDir: '根目录',
      rootDirDesc: '浏览所有文件',
      mediaDir: 'Media 文件',
      mediaDirDesc: '截图、图片、视频',
      workspaceDir: 'Workspace',
      workspaceDirDesc: '工作目录文件',
      otherSection: '其他',
      dashboard: 'Dashboard',
      dashboardDesc: '完整控制面板 (18789)',
      configDoc: '配置说明',
      configDocDesc: '访问地址、端口转发配置',
      clearHistory: '清除历史',
      clearHistoryDesc: '清除本地聊天记录',
      logout: '退出登录',
      logoutDesc: '清除登录状态，重新连接',
      
      // 消息
      thinking: '思考过程',
      toolCall: '工具调用',
      toolRunning: '执行中',
      toolDone: '完成',
      toolError: '失败',
      
      // 错误
      wsNotConnected: 'WebSocket 未连接',
      loginExpired: '登录已过期，请重新连接',
      imageTooLarge: '图片太大，请选择小于10MB的图片',
      uploadFailed: '上传失败',
      
      // 时间
      justNow: '刚刚',
      minutesAgo: '分钟前',
      hoursAgo: '小时前',
      
      // 语言
      langSwitch: 'EN',
      langName: '中文'
    },
    
    'en-US': {
      // General
      appName: 'XiaoQiang AI',
      appDesc: 'AI Family Assistant',
      
      // Login
      wsUrlPlaceholder: 'WebSocket URL',
      proxyUrlPlaceholder: 'Proxy URL',
      tokenPlaceholder: 'Access Token',
      sessionPlaceholder: 'Session ID',
      connectBtn: 'Connect',
      connecting: 'Connecting...',
      connectFailed: 'Connection failed',
      
      // Header
      sessionLabel: 'Session',
      refreshBtn: 'Refresh messages',
      menuBtn: 'Menu',
      
      // Working status
      working: 'Working...',
      
      // Input
      msgPlaceholder: 'Send message...',
      sendImageBtn: 'Send image',
      removeImageBtn: 'Remove image',
      previewAlt: 'Preview',
      
      // Menu
      menuTitle: '📋 Menu',
      chatSection: 'Chat',
      sessionList: 'Session List',
      sessionListDesc: 'Sessions in last 24 hours',
      currentSession: 'Current session',
      fileSection: 'File Browser',
      rootDir: 'Root',
      rootDirDesc: 'Browse all files',
      mediaDir: 'Media Files',
      mediaDirDesc: 'Screenshots, images, videos',
      workspaceDir: 'Workspace',
      workspaceDirDesc: 'Working directory files',
      otherSection: 'Other',
      dashboard: 'Dashboard',
      dashboardDesc: 'Full control panel (18789)',
      configDoc: 'Configuration',
      configDocDesc: 'Access URL, port forwarding config',
      clearHistory: 'Clear History',
      clearHistoryDesc: 'Clear local chat history',
      logout: 'Logout',
      logoutDesc: 'Clear login state, reconnect',
      
      // Messages
      thinking: 'Thinking',
      toolCall: 'Tool Call',
      toolRunning: 'Running',
      toolDone: 'Done',
      toolError: 'Error',
      
      // Errors
      wsNotConnected: 'WebSocket not connected',
      loginExpired: 'Login expired, please reconnect',
      imageTooLarge: 'Image too large, please select one under 10MB',
      tooManyImages: 'Maximum 9 images allowed',
      uploadFailed: 'Upload failed',
      
      // Time
      justNow: 'Just now',
      minutesAgo: 'minutes ago',
      hoursAgo: 'hours ago',
      
      // Language
      langSwitch: '中',
      langName: 'English'
    }
  },
  
  // 获取当前语言
  getLang() {
    return this.currentLang;
  },
  
  // 设置语言
  setLang(lang) {
    if (this.languages[lang]) {
      this.currentLang = lang;
      localStorage.setItem('oc_lang', lang);
      this.updateUI();
      return true;
    }
    return false;
  },
  
  // 切换语言
  toggleLang() {
    const newLang = this.currentLang === 'zh-CN' ? 'en-US' : 'zh-CN';
    return this.setLang(newLang);
  },
  
  // 获取文本
  t(key) {
    const lang = this.languages[this.currentLang];
    return lang[key] || key;
  },
  
  // 初始化语言
  init() {
    const savedLang = localStorage.getItem('oc_lang');
    if (savedLang && this.languages[savedLang]) {
      this.currentLang = savedLang;
    }
    
    // 从配置文件读取应用名称（如果存在）
    if (typeof window.OPENCLAW_CONFIG !== 'undefined' && OPENCLAW_CONFIG.app) {
      if (this.currentLang === 'zh-CN') {
        this.languages['zh-CN'].appName = OPENCLAW_CONFIG.app.appName || this.languages['zh-CN'].appName;
        this.languages['zh-CN'].appDesc = OPENCLAW_CONFIG.app.appDesc || this.languages['zh-CN'].appDesc;
      } else {
        this.languages['en-US'].appName = OPENCLAW_CONFIG.app.appNameEn || this.languages['en-US'].appName;
        this.languages['en-US'].appDesc = OPENCLAW_CONFIG.app.appDescEn || this.languages['en-US'].appDesc;
      }
    }
    
    this.updateUI();
  },
  
  // 更新 UI
  updateUI() {
    // 更新所有带有 data-i18n 属性的元素
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      el.textContent = this.t(key);
    });
    
    // 更新所有带有 data-i18n-placeholder 属性的元素
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      el.placeholder = this.t(key);
    });
    
    // 更新所有带有 data-i18n-title 属性的元素
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      el.title = this.t(key);
    });
    
    // 更新语言切换按钮
    const langBtn = document.getElementById('langBtn');
    if (langBtn) {
      langBtn.textContent = this.t('langSwitch');
    }
  }
};

// 导出到全局
if (typeof window !== 'undefined') {
  window.i18n = i18n;
}
