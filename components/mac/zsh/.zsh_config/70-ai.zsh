# =========================
# AI 工具 CLI 路径配置
# =========================

# Qoder CLI（AI 代码助手命令行工具）
path_prepend "$HOME/.local/bin"

# =========================
# 代码补全默认值（指向 litellm 网关）
# 实际密钥/URL 由 ~/.env 提供（LITELLM_BASE_URL 等）
# =========================

export AUTOCOMPLETE_API_BASE="${AUTOCOMPLETE_API_BASE:-${LITELLM_BASE_URL}}"
export AUTOCOMPLETE_MODEL="${AUTOCOMPLETE_MODEL:-${LITELLM_AUTOCOMPLETE_MODEL_OPENAI}}"
export AUTOCOMPLETE_API_KEY="${AUTOCOMPLETE_API_KEY:-${LITELLM_MASTER_KEY}}"
