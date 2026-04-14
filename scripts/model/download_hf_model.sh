#!/usr/bin/env bash
# scripts/model/download_hf_model.sh
# 从 Hugging Face 下载模型并导入指定目录（如 OMLX 模型路径）
# 支持通过本地代理下载

set -euo pipefail

# ===== 默认值 =====
DEFAULT_OUTPUT_DIR="${HOME}/.ollama/models/hf"
DEFAULT_INCLUDE_GGUF=false

# ===== 颜色输出 =====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ===== 使用帮助 =====
usage() {
    cat <<EOF
用法: $(basename "$0") [选项] <模型ID>

从 Hugging Face 下载模型并保存到指定目录。

参数:
  <模型ID>              Hugging Face 模型 ID，如 meta-llama/Llama-3.2-3B

选项:
  -p, --proxy PROXY     HTTP 代理地址，如 http://127.0.0.1:7890
  -o, --output DIR      输出目录（默认: ${DEFAULT_OUTPUT_DIR}）
  -r, --revision REV    模型版本/分支（默认: main）
  -t, --token TOKEN     Hugging Face token（或设置 HF_TOKEN 环境变量）
  --include GGUF_PAT    仅下载匹配 GGUF 模式文件，如 '*Q4_K_M*'
  --exclude PATTERN     排除匹配的文件模式（可多次使用）
  -f, --force           覆盖已存在的目录
  --dry-run             仅打印下载计划，不实际执行
  -h, --help            显示帮助

示例:
  # 通过本地代理下载模型到 OMLX 路径
  $(basename "$0") -p http://127.0.0.1:7890 \\
      -o /Users/zhehan/Library/Containers/com.apple.OMLLMApp/Data/models \\
      Qwen/Qwen2.5-7B-Instruct

  # 仅下载 GGUF Q4_K_M 量化文件
  $(basename "$0") -p http://127.0.0.1:7890 \\
      --include '*Q4_K_M*' \\
      bartowski/Llama-3.2-3B-Instruct-GGUF

  # 使用 token 下载 gated 模型
  $(basename "$0") -t hf_xxxxx -o /path/to/models \\
      meta-llama/Llama-3.2-3B-Instruct
EOF
    exit 0
}

# ===== 参数解析 =====
PROXY=""
OUTPUT_DIR=""
REVISION="main"
TOKEN=""
INCLUDE_PATTERN=""
EXCLUDE_PATTERNS=()
FORCE=false
DRY_RUN=false
MODEL_ID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--proxy)
            PROXY="$2"; shift 2 ;;
        -o|--output)
            OUTPUT_DIR="$2"; shift 2 ;;
        -r|--revision)
            REVISION="$2"; shift 2 ;;
        -t|--token)
            TOKEN="$2"; shift 2 ;;
        --include)
            INCLUDE_PATTERN="$2"; shift 2 ;;
        --exclude)
            EXCLUDE_PATTERNS+=("$2"); shift 2 ;;
        -f|--force)
            FORCE=true; shift ;;
        --dry-run)
            DRY_RUN=true; shift ;;
        -h|--help)
            usage ;;
        -*)
            error "未知选项: $1"
            usage ;;
        *)
            MODEL_ID="$1"; shift ;;
    esac
done

# ===== 参数校验 =====
if [[ -z "$MODEL_ID" ]]; then
    error "缺少模型 ID 参数"
    usage
fi

OUTPUT_DIR="${OUTPUT_DIR:-$DEFAULT_OUTPUT_DIR}"
TARGET_DIR="${OUTPUT_DIR}/${MODEL_ID}"

# ===== 前置检查 =====
HF_CLI_CMD=""

check_prerequisites() {
    info "检查前置依赖..."

    # 优先使用新版 hf CLI，回退到旧版 huggingface-cli
    if command -v hf &>/dev/null; then
        HF_CLI_CMD="hf"
        local hf_version
        hf_version=$(hf version 2>/dev/null || echo "unknown")
        info "使用新版 hf CLI: ${hf_version}"
    elif command -v huggingface-cli &>/dev/null; then
        HF_CLI_CMD="huggingface-cli"
        local hf_version
        hf_version=$(huggingface-cli version 2>/dev/null | head -1 || echo "unknown")
        info "使用旧版 huggingface-cli: ${hf_version}"
    else
        error "未找到 HF CLI（hf 或 huggingface-cli），请先安装："
        echo "  pip install -U huggingface_hub[cli]"
        echo "  或 pipx install huggingface_hub"
        exit 1
    fi
}

# ===== 构建下载命令 =====
build_download_cmd() {
    local cmd="${HF_CLI_CMD} download ${MODEL_ID}"
    cmd+=" --revision ${REVISION}"
    cmd+=" --local-dir ${TARGET_DIR}"

    # Token
    if [[ -n "$TOKEN" ]]; then
        cmd+=" --token ${TOKEN}"
    elif [[ -n "${HF_TOKEN:-}" ]]; then
        cmd+=" --token ${HF_TOKEN}"
    fi

    # Include pattern
    if [[ -n "$INCLUDE_PATTERN" ]]; then
        cmd+=" --include ${INCLUDE_PATTERN}"
    fi

    # Exclude patterns
    for pat in "${EXCLUDE_PATTERNS[@]+"${EXCLUDE_PATTERNS[@]}"}"; do
        cmd+=" --exclude ${pat}"
    done

    echo "$cmd"
}

# ===== 主流程 =====
main() {
    check_prerequisites

    info "模型 ID:    ${MODEL_ID}"
    info "输出目录:   ${TARGET_DIR}"
    info "版本:       ${REVISION}"

    if [[ -n "$PROXY" ]]; then
        info "代理:       ${PROXY}"
    fi

    if [[ "$INCLUDE_PATTERN" != "" ]]; then
        info "包含模式:   ${INCLUDE_PATTERN}"
    fi

    # 检查目标目录是否已存在
    if [[ -d "$TARGET_DIR" ]] && [[ "$FORCE" != true ]]; then
        error "目标目录已存在: ${TARGET_DIR}"
        echo "  使用 --force 覆盖，或选择其他输出目录"
        exit 1
    fi

    # Dry run
    if [[ "$DRY_RUN" == true ]]; then
        info "[Dry Run] 将执行:"
        build_download_cmd
        info "完成（未实际执行）"
        exit 0
    fi

    # 确保父目录存在
    mkdir -p "$(dirname "$TARGET_DIR")"

    # 如果启用 --force 且目录已存在，先删除
    if [[ -d "$TARGET_DIR" ]] && [[ "$FORCE" == true ]]; then
        warn "强制覆盖: 删除已存在的目录 ${TARGET_DIR}"
        rm -rf "$TARGET_DIR"
    fi

    # 执行下载
    info "开始下载..."
    local download_cmd
    download_cmd=$(build_download_cmd)

    # 如果设置了代理，通过环境变量传递
    if [[ -n "$PROXY" ]]; then
        info "通过代理下载..."
        HTTPS_PROXY="$PROXY" HTTP_PROXY="$PROXY" eval "$download_cmd"
    else
        eval "$download_cmd"
    fi

    # ===== 下载后验证 =====
    info "下载完成，验证文件..."
    local file_count
    file_count=$(find "$TARGET_DIR" -type f | wc -l | tr -d ' ')

    if [[ "$file_count" -eq 0 ]]; then
        error "下载目录为空，可能下载失败"
        exit 1
    fi

    info "文件数: ${file_count}"

    # 显示目录大小
    local dir_size
    dir_size=$(du -sh "$TARGET_DIR" | cut -f1)
    info "目录大小: ${dir_size}"

    # 列出关键文件
    info "关键文件:"
    for pattern in "*.safetensors" "*.gguf" "*.bin" "tokenizer.model" "config.json"; do
        local matches
        matches=$(find "$TARGET_DIR" -maxdepth 1 -name "$pattern" -type f 2>/dev/null || true)
        if [[ -n "$matches" ]]; then
            echo "$matches" | while read -r f; do
                local size
                size=$(du -sh "$f" | cut -f1)
                echo "  ${size}  $(basename "$f")"
            done
        fi
    done

    echo ""
    info "模型已保存到: ${TARGET_DIR}"

    # OMLX 提示
    if [[ "$OUTPUT_DIR" == *"OML"* ]] || [[ "$OUTPUT_DIR" == *"ollama"* ]]; then
        info "检测到 OMLX/Ollama 路径，确保格式兼容..."
        if find "$TARGET_DIR" -maxdepth 1 -name "*.safetensors" -type f -print -quit 2>/dev/null | grep -q .; then
            warn "检测到 safetensors 格式，OMLX 可能需要 GGUF 格式"
            info "建议使用 --include '*Q4*' 下载 GGUF 量化版本，或使用工具转换"
        fi
    fi
}

main "$@"
