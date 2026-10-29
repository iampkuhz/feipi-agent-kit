# Feipi Agent Kit Makefile
# 仓库级包装命令：
# - `make install-links`：过滤安装到用户级 agent 目录（入口实拷、运行目录链接）
# - `make install-project PROJECT=/path/to/project`：拷贝安装到项目目录
# - `make install`：兼容旧入口；未传项目路径时等价于 `install-links`
# - `make <service>-up`：启动服务
# - `make <service>-down`：停止服务

SHELL := /bin/bash
AGENT ?=
PROJECT ?=
DIR ?=
VERBOSE ?= 0
COLOR ?= auto
INSTALL_SCRIPT := ./scripts/install_skills.sh
INSTALL_OUTPUT_FLAGS = $(if $(filter 1,$(VERBOSE)),--verbose) --color "$(COLOR)"

# 解析路径
RESOLVED_PROJECT := $(or $(PROJECT),$(DIR))

# Services
SEARXNG_DIR := tools/search/searxng
LITELLM_DIR := tools/gateway/litellm
CRAWL4AI_DIR := tools/crawl/crawl4ai
OTEL_DIR := tools/gateway/otel

.PHONY: help install install-links install-project
.PHONY: searxng-up searxng-down searxng-restart searxng-logs
.PHONY: litellm-up litellm-down litellm-restart litellm-logs
.PHONY: searxng-mcp-run searxng-mcp-http searxng-mcp-test  # [已退役]
.PHONY: doctor setup
.PHONY: searxng-status litellm-status
.PHONY: crawl4ai-up crawl4ai-down crawl4ai-restart crawl4ai-logs crawl4ai-status
.PHONY: otel-up otel-down otel-restart otel-logs otel-status
.PHONY: model-download
.PHONY: harness-doctor validate-harness

# ===== 主帮助 =====

help:
	@echo "Feipi Agent Kit - 可用命令"
	@echo ""
	@echo "===== Skills 管理 ====="
	@echo "  make install-links [AGENT=codex|qwen|qoder|claudecode|openclaw]"
	@echo "  make install-project PROJECT=/path/to/project [AGENT=...]"
	@echo "  make install [AGENT=...] [PROJECT=/path/to/project|DIR=/path/to/project]"
	@echo "  输出选项：VERBOSE=1 查看跳过明细；COLOR=auto|always|never 控制颜色"
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
	@echo "  make searxng-mcp-run     # [已退役] SearXNG MCP 服务已移除"
	@echo "  make searxng-mcp-http    # [已退役] SearXNG MCP 服务已移除"
	@echo "  make searxng-mcp-test    # [已退役] SearXNG MCP 服务已移除"
	@echo ""
	@echo "===== 模型管理 ====="
	@echo "  make model-download MODEL=<id> [PROXY=<url>] [OUTPUT=<dir>]"
	@echo "                         # 从 Hugging Face 下载模型"
	@echo ""
	@echo "===== 仓库维护 ====="
	@echo "  make setup               # 只读检查 Podman、新机依赖与服务定义"
	@echo "  make crawl4ai-up / down / restart / logs / status"
	@echo "  make otel-up / down / restart / logs / status"
	@echo "  make doctor              # 健康检查"
	@echo ""
	@echo "===== Harness 验证 ====="
	@echo "  make harness-doctor      # 离线 harness 验证（rules/commands/registry/manifest）"
	@echo "  make validate-harness    # 同 harness-doctor"
	@echo ""

# ===== Skills 安装 =====

install:
ifeq ($(strip $(RESOLVED_PROJECT)),)
	@$(MAKE) --no-print-directory install-links AGENT="$(AGENT)"
else
	@$(MAKE) --no-print-directory install-project AGENT="$(AGENT)" PROJECT="$(RESOLVED_PROJECT)"
endif

install-links:
	@$(INSTALL_SCRIPT) $(if $(AGENT),--agent "$(AGENT)") $(INSTALL_OUTPUT_FLAGS)

install-project:
	@if [[ -z "$(RESOLVED_PROJECT)" ]]; then \
		echo "缺少 PROJECT=/path/to/project（兼容旧参数：DIR=/path/to/project）" >&2; \
		exit 1; \
	fi
	@$(INSTALL_SCRIPT) $(if $(AGENT),--agent "$(AGENT)") --dir "$(RESOLVED_PROJECT)" $(INSTALL_OUTPUT_FLAGS)

# ===== 本地服务：统一复用各服务脚本，不再绕到 Docker =====

searxng-up searxng-down searxng-restart searxng-logs searxng-status:
	@bash "$(SEARXNG_DIR)/scripts/searxng.sh" "$(patsubst searxng-%,%,$@)"

litellm-up litellm-down litellm-restart litellm-logs litellm-status:
	@bash "$(LITELLM_DIR)/scripts/litellm.sh" "$(patsubst litellm-%,%,$@)"

crawl4ai-up crawl4ai-down crawl4ai-restart crawl4ai-logs crawl4ai-status:
	@bash "$(CRAWL4AI_DIR)/scripts/crawl4ai.sh" "$(patsubst crawl4ai-%,%,$@)"

# OTel 的 restart 显式重建容器以应用配置，不清理本机日志。
otel-up otel-down otel-restart otel-logs otel-status:
	@bash "$(OTEL_DIR)/scripts/otel.sh" "$(patsubst otel-%,%,$@)"

# SearXNG MCP 服务 [已退役]
# tools/search/searxng-mcp/ 已于 2026-05 移除。以下 target 保留仅作提示。

searxng-mcp-run:
	@echo "[已退役] SearXNG MCP 服务（tools/search/searxng-mcp/）已移除"
	@echo "如需网页搜索能力，请使用 Crawl4AI MCP（tools/crawl/crawl4ai/）"

searxng-mcp-http:
	@echo "[已退役] SearXNG MCP 服务（tools/search/searxng-mcp/）已移除"

searxng-mcp-test:
	@echo "[已退役] SearXNG MCP 服务（tools/search/searxng-mcp/）已移除"

# ===== 仓库维护 =====

# 依赖和服务失败必须保留非零退出码，不能在失败后打印“初始化完成”。
setup:
	@bash scripts/bootstrap/setup.sh

doctor:
	@bash scripts/doctor/check.sh

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

# ===== Harness 验证 =====

harness-doctor:
	@bash scripts/harness/doctor.sh

validate-harness:
	@bash scripts/harness/doctor.sh
