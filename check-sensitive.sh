#!/bin/bash

# OpenClaw Mobile 敏感信息检查脚本
# 用于在发布前检查代码中是否包含敏感信息

echo "================================"
echo "OpenClaw Mobile 敏感信息检查"
echo "================================"
echo ""

FOUND_ISSUES=0

# 获取所有 Git 跟踪的文件
echo "检查范围: 所有 Git 跟踪的文件"
echo ""

TRACKED_FILES=$(git ls-files 2>/dev/null)

if [ -z "$TRACKED_FILES" ]; then
    echo "⚠️  未找到 Git 跟踪的文件，检查当前目录"
    TRACKED_FILES="mobile.html server.py config.js README.md README_CN.md docs/*.md config.example.js server_config.example.py"
fi

# 1. 检查 Token
echo "1. 检查 Token..."
if echo "$TRACKED_FILES" | xargs grep -rE "a-[A-Za-z0-9]{32,}" 2>/dev/null | grep -v "YOUR_GATEWAY_TOKEN" | grep -v "YOUR_TOKEN" | grep -v "example"; then
    echo "   ❌ 发现硬编码 Token！"
    FOUND_ISSUES=$((FOUND_ISSUES + 1))
else
    echo "   ✅ 未发现硬编码 Token"
fi

# 2. 检查 Tailscale IP (100.x.x.x)
echo ""
echo "2. 检查 Tailscale IP 地址..."
if echo "$TRACKED_FILES" | xargs grep -rE "100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}" 2>/dev/null | grep -v "100\.x\.x\.x" | grep -v "100\.\[0-9\]" | grep -v "example"; then
    echo "   ❌ 发现真实 Tailscale IP！"
    FOUND_ISSUES=$((FOUND_ISSUES + 1))
else
    echo "   ✅ 未发现真实 Tailscale IP"
fi

# 3. 检查 Tailscale 域名
echo ""
echo "3. 检查 Tailscale 域名..."
if echo "$TRACKED_FILES" | xargs grep -rE "[a-z0-9-]+\.tail[a-z0-9]+\.ts\.net" 2>/dev/null | grep -v "tailXXXX" | grep -v "your-hostname" | grep -v "example"; then
    echo "   ❌ 发现硬编码 Tailscale 域名！"
    FOUND_ISSUES=$((FOUND_ISSUES + 1))
else
    echo "   ✅ 未发现硬编码 Tailscale 域名"
fi

# 4. 检查 Tailnet ID
echo ""
echo "4. 检查 Tailnet ID..."
if echo "$TRACKED_FILES" | xargs grep -rE "tail[a-z0-9]{4,}\.ts\.net" 2>/dev/null | grep -v "tailXXXX" | grep -v "example" | grep -v "ts\.net"; then
    echo "   ❌ 发现真实 Tailnet ID！"
    FOUND_ISSUES=$((FOUND_ISSUES + 1))
else
    echo "   ✅ 未发现真实 Tailnet ID"
fi

# 5. 检查云服务商域名前缀
echo ""
echo "5. 检查云转发域名前缀..."
if echo "$TRACKED_FILES" | xargs grep -rE "forward-[a-z]+-[0-9]+\.orcaterm" 2>/dev/null | grep -v "forward-http-xxx" | grep -v "forward-wss-xxx" | grep -v "example"; then
    echo "   ❌ 发现真实云转发域名！"
    FOUND_ISSUES=$((FOUND_ISSUES + 1))
else
    echo "   ✅ 未发现真实云转发域名"
fi

# 6. 检查 orcaterm 域名（排除示例）
echo ""
echo "6. 检查 orcaterm 域名..."
# 只检查实际域名前缀（forward-xxx-123 格式），不检查域名后缀和示例
if echo "$TRACKED_FILES" | xargs grep -rE "forward-[a-z]{6,}-[0-9]+\.orcaterm" 2>/dev/null | grep -v "forward-http-xxx" | grep -v "forward-wss-xxx"; then
    echo "   ❌ 发现真实云转发域名前缀！"
    FOUND_ISSUES=$((FOUND_ISSUES + 1))
else
    echo "   ✅ 未发现真实云转发域名前缀"
fi

# 7. 检查是否有示例配置
echo ""
echo "7. 检查示例配置文件..."
if [ -f "config.example.js" ]; then
    echo "   ✅ 存在 config.example.js"
else
    echo "   ⚠️  缺少 config.example.js"
fi

if [ -f ".gitignore" ]; then
    echo "   ✅ 存在 .gitignore"
    if grep -q "config.js" .gitignore; then
        echo "   ✅ .gitignore 包含 config.js"
    else
        echo "   ⚠️  .gitignore 不包含 config.js"
    fi
else
    echo "   ⚠️  缺少 .gitignore"
fi

# 总结
echo ""
echo "================================"
if [ $FOUND_ISSUES -eq 0 ]; then
    echo "✅ 检查通过！未发现敏感信息"
    echo ""
    echo "后续步骤："
    echo "1. 确认所有配置使用占位符"
    echo "2. 检查文档中的示例是否为通用示例"
    echo "3. 再次人工审查代码"
    echo "4. 提交代码: git add -A && git commit -m 'xxx'"
else
    echo "❌ 发现 $FOUND_ISSUES 个安全问题"
    echo ""
    echo "请修复上述问题后再发布！"
    echo ""
    echo "常见修复方法："
    echo "- Tailscale 域名: your-hostname.tailXXXX.ts.net"
    echo "- Tailscale IP: 100.x.x.x"
    echo "- 云转发域名: forward-http-xxx.orcaterm.cloud.tencent.com"
    echo "- Token: YOUR_GATEWAY_TOKEN_HERE"
    exit 1
fi
