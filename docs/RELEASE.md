# 发布指南

本文档说明如何将 OpenClaw Mobile 发布到 GitHub。

## 发布前检查清单

### 1. 敏感信息检查 ✅

```bash
cd openclaw-mobile-release
./check-sensitive.sh
```

确保所有检查通过。

### 2. 手动审查

- [ ] 检查 `mobile.html` - 确认没有硬编码的 Token、IP、域名
- [ ] 检查 `server.py` - 确认没有敏感配置
- [ ] 检查所有 `.md` 文件 - 确认示例使用通用占位符
- [ ] 检查 `config.example.js` - 确认是模板而非真实配置

### 3. 代码质量

- [ ] 代码格式化
- [ ] 注释完整
- [ ] 无调试代码
- [ ] 无 console.log（可选）

### 4. 文档完整性

- [ ] README.md 完整
- [ ] docs/DEPLOYMENT.md 完整
- [ ] docs/CONFIGURATION.md 完整
- [ ] docs/SECURITY.md 完整

### 5. 功能测试

- [ ] 本地测试通过
- [ ] Token 从用户输入获取
- [ ] 自动登录功能正常
- [ ] WebSocket 连接正常
- [ ] 消息收发正常

## Git 操作

### 1. 初始化仓库

```bash
cd openclaw-mobile-release

# 初始化 Git
git init

# 添加文件
git add .

# 提交
git commit -m "Initial commit: OpenClaw Mobile v1.0.0

Features:
- Modern mobile-friendly UI
- Real-time chat with WebSocket
- Auto-reconnect on network change
- Login state persistence (1 hour)
- File browser
- Thinking process display
- Tool call visualization
- Tencent Cloud port forwarding support

Security:
- No hardcoded tokens
- No hardcoded IPs
- No hardcoded domains
- Security documentation included
"
```

### 2. 创建 GitHub 仓库

1. 访问 https://github.com/new
2. 仓库名称：`openclaw-mobile`
3. 描述：`Modern mobile web interface for OpenClaw Gateway`
4. 可见性：Public
5. **不要**勾选 "Initialize with README"（我们已经有了）
6. 点击 "Create repository"

### 3. 推送到 GitHub

```bash
# 添加远程仓库
git remote add origin https://github.com/YOUR_USERNAME/openclaw-mobile.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

### 4. 创建 Release

```bash
# 创建标签
git tag -a v1.0.0 -m "Release v1.0.0

First public release of OpenClaw Mobile.

Features:
- Modern UI with dark theme
- WebSocket real-time communication
- Auto-reconnect
- Login persistence
- File browser
- Multi-environment support
"

# 推送标签
git push origin v1.0.0
```

然后在 GitHub 上：
1. 进入仓库页面
2. 点击 "Releases"
3. 点击 "Create a new release"
4. 选择标签 `v1.0.0`
5. 填写发布说明
6. 点击 "Publish release"

## 版本号规范

使用语义化版本号：`MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向后兼容的功能新增
- **PATCH**: 向后兼容的问题修复

示例：
- `v1.0.0` - 首次发布
- `v1.1.0` - 新增功能（如：支持新的云服务商）
- `v1.0.1` - Bug 修复（如：修复重连问题）

## 发布后

### 1. 更新 OpenClaw 文档

在 OpenClaw 主仓库中添加链接：
```markdown
## 相关项目

- [OpenClaw Mobile](https://github.com/YOUR_USERNAME/openclaw-mobile) - 移动端 Web 界面
```

### 2. 社区宣传

- 在 OpenClaw Discord 分享
- 在 Twitter/X 发布
- 写博客文章介绍

### 3. 收集反馈

- 关注 GitHub Issues
- 回复用户问题
- 记录功能请求

## 持续维护

### 定期检查

- [ ] 每月检查依赖更新
- [ ] 每月检查安全问题
- [ ] 及时回复 Issues
- [ ] 定期更新文档

### 版本更新流程

1. 修改代码
2. 更新版本号
3. 运行 `check-sensitive.sh`
4. 更新 CHANGELOG.md
5. 提交 PR 或直接提交
6. 创建新的 Release

## 安全公告

如果发现安全漏洞：

1. **不要**在公开 Issue 中发布
2. 通过私密渠道报告
3. 等待修复后再公开
4. 发布安全公告

---

**恭喜！** 你已经完成了 OpenClaw Mobile 的发布准备工作！
