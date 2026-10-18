#!/bin/bash
# Feipi Agent Kit 健康检查脚本
# 用法：./scripts/doctor/check.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$REPO_ROOT"

echo "🏥 Feipi Agent Kit 健康检查"
echo "======================="
echo ""

ERRORS=0
WARNINGS=0

# ===== 检查环境配置 =====

echo "📋 环境配置检查"
echo "---------------"

# 检查 .env 文件
if [[ -f "$REPO_ROOT/.env" ]]; then
    echo "✅ .env 存在"
else
    echo "ℹ️  根 .env 未创建（可选参考文件，服务脚本不自动加载）"
fi

# 检查关键环境变量
check_env_var() {
    local var=$1
    if [[ -n "${!var}" ]]; then
        echo "✅ $var 已设置"
    else
        echo "⚠️  $var 未设置"
        WARNINGS=$((WARNINGS + 1))
    fi
}

echo ""
echo "关键环境变量："
check_env_var "SEARXNG_BASE_URL"

# ===== 检查服务状态 =====

echo ""
echo "🔌 服务状态检查"
echo "---------------"

# SearXNG
echo -n "SearXNG: "
if curl --noproxy '*' -fsS --max-time 2 http://127.0.0.1:8873/healthz > /dev/null; then
    echo "✅ 运行中 (http://localhost:8873)"
else
    echo "❌ 未运行"
    echo "   启动命令：make searxng-up"
    ERRORS=$((ERRORS + 1))
fi

# LiteLLM
echo -n "LiteLLM: "
if curl --noproxy '*' -fsS --max-time 2 http://127.0.0.1:4000/health/readiness > /dev/null; then
    echo "✅ 运行中 (http://localhost:4000)"
else
    echo "❌ 未运行"
    echo "   启动命令：make litellm-up"
    ERRORS=$((ERRORS + 1))
fi

# ===== 检查目录结构 =====

echo ""
echo "📁 目录结构检查"
echo "---------------"

check_dir() {
    local dir=$1
    local name=$2
    if [[ -d "$REPO_ROOT/$dir" ]]; then
        echo "✅ $name: $dir"
    else
        echo "❌ $name 缺失：$dir"
        ERRORS=$((ERRORS + 1))
    fi
}

check_dir "skills" "Skills"
check_dir "rules" "Rules"
check_dir "commands" "Commands"
check_dir "runtimes" "Runtimes"
check_dir "tools" "Tools"

echo ""
echo "服务目录："
check_dir "tools/search/searxng" "SearXNG"
check_dir "tools/gateway/litellm" "LiteLLM"
# searxng-mcp 已退役（tools/search/searxng-mcp/ 于 2026-05 移除）

# ===== 检查文件权限 =====

echo ""
echo "🔐 文件权限检查"
echo "---------------"

check_executable() {
    local file=$1
    if [[ -x "$REPO_ROOT/$file" ]]; then
        echo "✅ 可执行：$file"
    else
        echo "⚠️ 不可执行：$file"
        WARNINGS=$((WARNINGS + 1))
    fi
}

check_executable "scripts/bootstrap/setup.sh"
check_executable "scripts/doctor/check.sh"
check_executable "tools/search/searxng/scripts/searxng.sh"
check_executable "tools/gateway/litellm/scripts/litellm.sh"
# searxng-mcp/scripts/run.sh 已随服务退役移除

# ===== 总结 =====

echo ""
echo "======================="
echo "检查结果："
echo "  错误：$ERRORS"
echo "  警告：$WARNINGS"
echo ""

if [[ $ERRORS -gt 0 ]]; then
    echo "❌ 发现问题，请先修复"
    exit 1
elif [[ $WARNINGS -gt 0 ]]; then
    echo "⚠️  存在警告，但不影响基本使用"
else
    echo "✅ 一切正常"
fi

echo ""
echo "===== 快速修复 ====="
echo ""
echo "启动所有服务："
echo "  make searxng-up"
echo "  make litellm-up"
echo ""
echo "配置覆盖请按各服务文档；LiteLLM 读取导出的变量，Crawl4AI 使用本机 .env.local。"
echo "新机重建步骤：docs/setup-new-mac.md"
echo ""
