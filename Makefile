# Agent Tools Makefile
# 仓库级包装命令：
# - `make install-links`：软链接安装到用户级 agent 目录
# - `make install-project PROJECT=/path/to/project`：拷贝安装到项目目录
# - `make install`：兼容旧入口；未传项目路径时等价于 `install-links`
# - `make <service>-up`：启动服务
# - `make <service>-down`：停止服务

SHELL := /bin/bash
AGENT ?=
PROJECT ?=
DIR ?=
INSTALL_SCRIPT := ./scripts/install_skills.sh

# 解析路径
RESOLVED_PROJECT := $(or $(PROJECT),$(DIR))

# Services
SEARXNG_DIR := tools/search/searxng
SEARXNG_MCP_DIR := tools/search/searxng-mcp
LITELLM_DIR := tools/gateway/litellm

.PHONY: help install install-links install-project
.PHONY: searxng-up searxng-down searxng-restart searxng-logs
.PHONY: litellm-up litellm-down litellm-restart litellm-logs
.PHONY: searxng-mcp-run searxng-mcp-http searxng-mcp-test
.PHONY: doctor setup
.PHONY: model-download

# ===== 主帮助 =====

help:
	@echo "Agent Tools - 可用命令"
	@echo ""
	@echo "===== Skills 管理 ====="
	@echo "  make install-links [AGENT=codex|qwen|qoder|claudecode|openclaw]"
	@echo "  make install-project PROJECT=/path/to/project [AGENT=...]"
	@echo "  make install [AGENT=...] [PROJECT=/path/to/project|DIR=/path/to/project]"
	@echo ""
	@echo "===== 服务管理 ====="
	@echo "  make searxng-up          # 启动 SearXNG 搜索引擎"
	@echo "  make searxng-down        # 停止 SearXNG"
	@echo "  make searxng-restart     # 重启 SearXNG"
	@echo "  make searxng-logs        # 查看 SearXNG 日志"
	@echo ""
	@echo "  make litellm-up          # 启动 LiteLLM 模型网关"
	@echo "  make litellm-down        # 停止 LiteLLM"
	@echo "  make litellm-restart     # 重启 LiteLLM"
	@echo "  make litellm-logs        # 查看 LiteLLM 日志"
	@echo ""
	@echo "  make searxng-mcp-run     # 运行 SearXNG MCP 服务（Stdio 模式）"
	@echo "  make searxng-mcp-http    # 运行 SearXNG MCP 服务（HTTP 模式）"
	@echo "  make searxng-mcp-test    # 测试 SearXNG MCP 服务"
	@echo ""
	@echo "===== 模型管理 ====="
	@echo "  make model-download MODEL=<id> [PROXY=<url>] [OUTPUT=<dir>]"
	@echo "                         # 从 Hugging Face 下载模型"
	@echo ""
	@echo "===== 仓库维护 ====="
	@echo "  make setup               # 初始化设置"
	@echo "  make doctor              # 健康检查"
	@echo ""

# ===== Skills 安装 =====

install:
ifeq ($(strip $(RESOLVED_PROJECT)),)
	@$(MAKE) install-links AGENT="$(AGENT)"
else
	@$(MAKE) install-project AGENT="$(AGENT)" PROJECT="$(RESOLVED_PROJECT)"
endif

install-links:
	@$(INSTALL_SCRIPT) $(if $(AGENT),--agent "$(AGENT)")

install-project:
	@if [[ -z "$(RESOLVED_PROJECT)" ]]; then \
		echo "缺少 PROJECT=/path/to/project（兼容旧参数：DIR=/path/to/project）" >&2; \
		exit 1; \
	fi
	@$(INSTALL_SCRIPT) $(if $(AGENT),--agent "$(AGENT)") --dir "$(RESOLVED_PROJECT)"

# ===== SearXNG 服务 =====

searxng-up:
	@echo "🚀 启动 SearXNG..."
	@cd $(SEARXNG_DIR) && docker compose -f compose/docker-compose.yml up -d
	@echo "✅ SearXNG 已启动"
	@echo "📌 访问地址：http://localhost:8873"
	@echo "📌 健康检查：curl http://localhost:8873/healthz"

searxng-down:
	@echo "🛑 停止 SearXNG..."
	@cd $(SEARXNG_DIR) && docker compose -f compose/docker-compose.yml down
	@echo "✅ SearXNG 已停止"

searxng-restart:
	@echo "🔄 重启 SearXNG..."
	@cd $(SEARXNG_DIR) && docker compose -f compose/docker-compose.yml restart
	@echo "✅ SearXNG 已重启"

searxng-logs:
	@cd $(SEARXNG_DIR) && docker compose -f compose/docker-compose.yml logs -f

# ===== LiteLLM 服务 =====

litellm-up:
	@echo "🚀 启动 LiteLLM..."
	@echo "⚠️  请确保已配置环境变量（source tools/gateway/litellm/env/.env 或手动 export）"
	@cd $(LITELLM_DIR) && docker compose -f compose/docker-compose.yml up -d
	@echo "✅ LiteLLM 已启动"
	@echo "📌 访问地址：http://localhost:4000"
	@echo "📌 健康检查：curl http://localhost:4000/health"

litellm-down:
	@echo "🛑 停止 LiteLLM..."
	@cd $(LITELLM_DIR) && docker compose -f compose/docker-compose.yml down
	@echo "✅ LiteLLM 已停止"

litellm-restart:
	@echo "🔄 重启 LiteLLM..."
	@cd $(LITELLM_DIR) && docker compose -f compose/docker-compose.yml restart
	@echo "✅ LiteLLM 已重启"

litellm-logs:
	@cd $(LITELLM_DIR) && docker compose -f compose/docker-compose.yml logs -f

# ===== SearXNG MCP 服务 =====

searxng-mcp-run:
	@echo "🚀 运行 SearXNG MCP 服务（Stdio 模式）..."
	@echo "📌 此模式用于 Claude Code MCP 集成"
	@cd $(SEARXNG_MCP_DIR) && ./scripts/run.sh stdio

searxng-mcp-http:
	@echo "🚀 运行 SearXNG MCP 服务（HTTP 模式）..."
	@cd $(SEARXNG_MCP_DIR) && ./scripts/run.sh http

searxng-mcp-test:
	@echo "🧪 测试 SearXNG MCP 服务..."
	@cd $(SEARXNG_MCP_DIR) && ./scripts/run.sh test

# ===== 仓库维护 =====

setup:
	@echo "🔧 初始化设置..."
	@./scripts/bootstrap/setup.sh 2>/dev/null || echo "⚠️  setup.sh 尚未创建，手动执行初始化"
	@echo "✅ 初始化完成"

doctor:
	@echo "🏥 健康检查..."
	@./scripts/doctor/check.sh 2>/dev/null || echo "⚠️  check.sh 尚未创建，手动执行检查"
	@echo ""
	@echo "===== 服务状态 ====="
	@echo "SearXNG:"
	@curl -s http://localhost:8873/healthz && echo "✅ 运行中" || echo "❌ 未运行"
	@echo ""
	@echo "LiteLLM:"
	@curl -s http://localhost:4000/health > /dev/null && echo "✅ 运行中" || echo "❌ 未运行"
	@echo ""
	@echo "SearXNG MCP:"
	@echo "  需要手动测试（在 Claude Code 中调用）"

# ===== 模型管理 =====

model-download:
	@if [[ -z "$(MODEL)" ]]; then \
		echo "❌ 缺少 MODEL 参数，用法: make model-download MODEL=<id> [PROXY=<url>] [OUTPUT=<dir>]" >&2; \
		exit 1; \
	fi
	@bash scripts/model/download_hf_model.sh \
		$(if $(PROXY),-p "$(PROXY)") \
		$(if $(OUTPUT),-o "$(OUTPUT)") \
		"$(MODEL)"
