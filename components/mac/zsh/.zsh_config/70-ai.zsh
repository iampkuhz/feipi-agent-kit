# =========================
# AI 工具 CLI 路径配置
# =========================

# 原生 oMLX 入口还会读取应用的数据目录设置；它优先于通用安装器的兼容入口。
# 这里有意保留尚不存在的目录：应用首次打开创建入口后即可识别，避免 Shell PATH 弹窗。
path=("$HOME/.omlx/bin" ${path:#"$HOME/.omlx/bin"})
export PATH

# =========================
# 代码补全默认值（指向 litellm 网关）
# 实际密钥/URL 由 ~/.env 提供（LITELLM_BASE_URL 等）
# =========================

export AUTOCOMPLETE_API_BASE="${AUTOCOMPLETE_API_BASE:-${LITELLM_BASE_URL:-}}"
export AUTOCOMPLETE_MODEL="${AUTOCOMPLETE_MODEL:-${LITELLM_AUTOCOMPLETE_MODEL_OPENAI:-}}"
export AUTOCOMPLETE_API_KEY="${AUTOCOMPLETE_API_KEY:-${LITELLM_MASTER_KEY:-}}"

# QODER_DISPATCHER_PATH v1
path=("$HOME/.qoder/entry" ${path:#"$HOME/.qoder/entry"})
export PATH
# END QODER_DISPATCHER_PATH v1
