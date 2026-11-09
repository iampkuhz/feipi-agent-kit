#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# PPTX → PNG 渲染脚本
# 用法: bash render_pptx.sh <input.pptx> <output_dir> [--json]
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -lt 2 ]]; then
  echo "用法: bash render_pptx.sh <input.pptx> <output_dir> [--json]"
  exit 1
fi

INPUT_PPTX_INPUT="$1"
case "$INPUT_PPTX_INPUT" in
  /*) ;;
  *) INPUT_PPTX_INPUT="$PWD/$INPUT_PPTX_INPUT" ;;
esac
INPUT_PPTX_DIR="$(cd "$(dirname "$INPUT_PPTX_INPUT")" && pwd -P)"
INPUT_PPTX="$INPUT_PPTX_DIR/$(basename "$INPUT_PPTX_INPUT")"
OUTPUT_DIR="$2"
JSON_MODE=""
if [[ "${3:-}" == "--json" ]]; then
  JSON_MODE="yes"
fi

if [[ ! -f "$INPUT_PPTX" ]]; then
  if [[ -z "$JSON_MODE" ]]; then
    echo "错误: PPTX 文件不存在: $INPUT_PPTX"
  else
    echo '{"status":"fail","error":"PPTX 文件不存在","renderer":"none"}'
  fi
  exit 2
fi

mkdir -p "$OUTPUT_DIR"

# --- 检测渲染引擎 ---
RENDERER=""
RENDER_CMD=()

if command -v soffice &>/dev/null; then
  RENDERER="soffice"
  RENDER_CMD=(soffice --headless)
elif command -v libreoffice >/dev/null 2>&1; then
  RENDERER="libreoffice"
  RENDER_CMD=(libreoffice --headless)
fi

if [[ -z "$RENDERER" ]]; then
  # macOS 应用包不一定把 soffice 加入 PATH，先用系统索引发现应用位置。
  if [[ "$(uname -s)" == "Darwin" ]] && command -v mdfind >/dev/null 2>&1; then
    while IFS= read -r app_path; do
      [[ -z "$app_path" ]] && continue
      candidate="$app_path/Contents/MacOS/soffice"
      if [[ -x "$candidate" ]]; then
        RENDERER="$candidate"
        RENDER_CMD=("$candidate" --headless)
        break
      fi
    done < <(mdfind 'kMDItemCFBundleIdentifier == "org.libreoffice.script"' 2>/dev/null)
  fi
fi

if [[ -z "$RENDERER" ]]; then
  if [[ -z "$JSON_MODE" ]]; then
    echo "跳过 PPTX 渲染: LibreOffice/soffice 未安装"
    echo "无法进行完整视觉 QA，需要安装 LibreOffice 才能渲染 PNG 截图。"
    echo "  macOS: brew install --cask libreoffice"
    echo "  Linux: apt-get install libreoffice 或 dnf install libreoffice"
  else
    # 输出 skip 状态供下游消费
    node "$SCRIPT_DIR/render_pptx.js" --skip "$INPUT_PPTX" "$OUTPUT_DIR"
  fi
  exit 100
fi

if [[ -z "$JSON_MODE" ]]; then
  echo "使用渲染引擎: $RENDERER"
fi

# --- 执行渲染 ---
# 策略 1: 直接转 PNG
# 策略 2: 先转 PDF 再转 PNG（如果策略 1 产出的图片异常）

TMPDIR_RENDER=$(mktemp -d)
trap 'rm -rf "$TMPDIR_RENDER"' EXIT

# 策略 1: PPTX → PNG 直接转换
"${RENDER_CMD[@]}" --convert-to png --outdir "$TMPDIR_RENDER" "$INPUT_PPTX" 2>/dev/null || true

# 检查直接转换是否产出了有效文件
PNG_COUNT=$(find "$TMPDIR_RENDER" -name '*.png' -size +1k 2>/dev/null | wc -l | tr -d ' ')

if [[ "$PNG_COUNT" -eq 0 ]]; then
  if [[ -z "$JSON_MODE" ]]; then
    echo "直接 PNG 转换未产生有效文件，尝试 PPTX → PDF → PNG 策略..."
  fi
  # 策略 2: PPTX → PDF → PNG
  "${RENDER_CMD[@]}" --convert-to pdf --outdir "$TMPDIR_RENDER" "$INPUT_PPTX" 2>/dev/null || true

  PDF_FILE=$(find "$TMPDIR_RENDER" -name '*.pdf' 2>/dev/null | head -1)
  if [[ -n "$PDF_FILE" ]]; then
    # 使用 sips (macOS 内置) 转 PNG
    if command -v sips &>/dev/null; then
      sips -s format png "$PDF_FILE" --out "$TMPDIR_RENDER/rendered.png" 2>/dev/null || true
    fi
    # 使用 convert (ImageMagick，可选)
    if [[ ! -f "$TMPDIR_RENDER/rendered.png" ]] && command -v convert &>/dev/null; then
      convert -density 150 "$PDF_FILE" "$TMPDIR_RENDER/rendered-%03d.png" 2>/dev/null || true
    fi
  fi
fi

# --- 移动结果到目标目录 ---
PNG_FILES=$(find "$TMPDIR_RENDER" -name '*.png' -size +0 2>/dev/null | sort)
COPIED=0
for png in $PNG_FILES; do
  base="$(basename "$png")"
  cp "$png" "$OUTPUT_DIR/$base"
  COPIED=$((COPIED + 1))
  if [[ -z "$JSON_MODE" ]]; then
    echo "  已导出: $base"
  fi
done

if [[ "$COPIED" -eq 0 ]]; then
  if [[ -z "$JSON_MODE" ]]; then
    echo "警告: 渲染未产生有效 PNG 文件。"
    echo "可能原因: PPTX 文件为空，或 LibreOffice 转换失败。"
  fi
  # 仍输出 manifest（status=fail），让下游处理
fi

# --- 生成 manifest ---
node "$SCRIPT_DIR/render_pptx.js" "$INPUT_PPTX" "$OUTPUT_DIR" "$RENDERER"
