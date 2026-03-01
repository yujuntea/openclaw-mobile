# 安全注意事项

⚠️ **重要**：在公开分享或部署 OpenClaw Mobile 之前，请务必仔细阅读本文档。

## 敏感信息清单

以下信息 **绝对不能** 包含在公开代码中：

| 类型 | 示例 | 位置 |
|------|------|------|
| Gateway Token | `a-xxxxxxxxxxxxxxxxxxxxxxxx` | mobile.html, config.js |
| 内网 IP | `100.x.x.x`, `192.168.x.x` | mobile.html, server.py |
| Tailscale 域名 | `your-host.tailXXXX.ts.net` | mobile.html, server.py |
| 端口转发域名 | `your-prefix.orcaterm.cloud.tencent.com` | mobile.html |
| 端口号 | `18789`, `8080` | 可保留，但建议配置化 |

## 清理检查清单

在公开代码之前，请确保：

### ✅ mobile.html

- [ ] Token 已替换为占位符或从用户输入获取
- [ ] 内网 IP 已移除或替换为 `localhost`
- [ ] Tailscale 域名已替换为通用示例
- [ ] 腾讯云域名映射已清空或使用示例
- [ ] Dashboard 链接使用动态检测或占位符

### ✅ server.py

- [ ] BIND_HOST 使用 `0.0.0.0` 或配置化
- [ ] 所有域名替换为占位符
- [ ] 内网 IP 已移除
- [ ] Gateway 地址使用 `127.0.0.1`

### ✅ README.html / 文档

- [ ] 所有示例域名使用 `example.com` 或类似占位符
- [ ] 所有 IP 使用私有地址段 `192.168.x.x` 或 `10.x.x.x`
- [ ] Token 使用 `YOUR_TOKEN_HERE` 等占位符

### ✅ 配置文件

- [ ] `config.js` 不包含真实 Token
- [ ] 提供 `config.example.js` 作为模板
- [ ] `.gitignore` 包含 `config.js`

## Gateway 安全配置

### 1. Token 管理

```bash
# 生成强 Token
openssl rand -base64 32

# 定期更换 Token（建议每月）
# 1. 生成新 Token
# 2. 更新 openclaw.json
# 3. 重启 Gateway
# 4. 通知所有用户更新
```

### 2. allowedOrigins 配置

```json
{
  "gateway": {
    "controlUi": {
      "allowedOrigins": [
        // ✅ 好：具体域名
        "https://your-domain.com",
        "http://your-host.tailXXXX.ts.net:8080",
        
        // ⚠️ 谨慎：通配符域名
        "*.your-domain.com",
        
        // ❌ 危险：不要使用通配符
        "*"
      ]
    }
  }
}
```

### 3. 网络绑定

```json
{
  "gateway": {
    "bind": "tailnet",  // ✅ 推荐：Tailscale 内网
    // "bind": "0.0.0.0",  // ❌ 危险：公网暴露
    // "bind": "loopback"  // ✅ 最安全：仅本地
  }
}
```

## 网络安全

### 1. 访问控制

```bash
# 使用防火墙限制访问
# 仅允许内网访问
iptables -A INPUT -p tcp --dport 8080 -s 192.168.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j DROP

# 仅允许 Tailscale 访问
iptables -A INPUT -p tcp --dport 8080 -i tailscale0 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j DROP
```

### 2. 使用 VPN

推荐使用 VPN 保护访问：

| VPN 方案 | 安全性 | 便利性 |
|----------|--------|--------|
| Tailscale | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| WireGuard | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| OpenVPN | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| ZeroTier | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

### 3. 云端口转发

使用云服务商端口转发时：

- ✅ 使用 HTTPS（端口 443）
- ✅ 配置域名映射
- ✅ 使用 WSS（WebSocket Secure）
- ❌ 不要暴露原始端口

## 代码审查

### 发布前检查

```bash
# 检查敏感信息（替换为你的实际敏感标识）
grep -r "your-tailnet-id\|100\.116\|your-token-prefix" . --exclude-dir=.git

# 检查硬编码 Token
grep -r "token.*=.*['\"][a-zA-Z0-9]\{20,\}['\"]" . --exclude-dir=.git

# 检查 IP 地址
grep -rE "[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}" . --exclude-dir=.git

# 检查域名（替换为你的实际域名）
grep -r "your-domain\.cloud\.tencent\.com\|tailXXXX\.ts\.net" . --exclude-dir=.git
```

### .gitignore 配置

```gitignore
# 配置文件
config.js
.env
*.local

# 日志
*.log

# 依赖
node_modules/

# 敏感文件
secrets/
*.pem
*.key
```

## 最佳实践

### 1. 最小权限原则

- Token 只给需要的人
- 定期审查 allowedOrigins
- 及时移除不再使用的域名

### 2. 监控和日志

```bash
# 启用 Gateway 日志
# 在 openclaw.json 中配置
{
  "gateway": {
    "logging": {
      "level": "info",
      "file": "/var/log/openclaw/gateway.log"
    }
  }
}

# 监控访问日志
tail -f /var/log/openclaw/gateway.log | grep -E "CONNECT|ERROR"
```

### 3. 备份和恢复

```bash
# 备份配置
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.backup

# 恢复配置
cp ~/.openclaw/openclaw.json.backup ~/.openclaw/openclaw.json
systemctl --user restart openclaw-gateway
```

## 应急响应

### Token 泄露

```bash
# 1. 立即更换 Token
NEW_TOKEN=$(openssl rand -base64 32)
jq ".gateway.auth.token = \"$NEW_TOKEN\"" ~/.openclaw/openclaw.json > /tmp/openclaw.json.new
mv /tmp/openclaw.json.new ~/.openclaw/openclaw.json

# 2. 重启 Gateway
systemctl --user restart openclaw-gateway

# 3. 通知所有用户
# 4. 审查访问日志
# 5. 检查异常行为
```

### 域名泄露

```bash
# 1. 从 allowedOrigins 移除泄露域名
# 2. 更换域名或关闭端口转发
# 3. 检查访问日志
# 4. 考虑更换端口
```

## 合规性

### GDPR

如果处理欧盟用户数据：

- 添加隐私政策链接
- 提供数据导出功能
- 提供数据删除功能
- 记录数据处理活动

### 数据保护

- 不要在日志中记录敏感数据
- 定期清理历史消息
- 提供用户数据删除选项

## 联系方式

如发现安全漏洞，请通过以下方式报告：

- GitHub Issues（公开问题）
- 私密报告：security@example.com

---

**记住**：安全是一个持续的过程，不是一次性的任务。定期审查和更新你的安全配置！
