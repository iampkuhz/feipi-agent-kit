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

# 直接转 PNG 只会得到第一页；先转 PDF，再由 Poppler 输出所有页面。
if ! command -v python3 >/dev/null 2>&1 || ! command -v pdftoppm >/dev/null 2>&1; then
  echo '渲染需要 Python 3 和 Poppler：macOS brew install python poppler；Linux 安装 python3 poppler-utils' >&2
  exit 100
fi
TMPDIR_RENDER="$(mktemp -d "${TMPDIR:-/tmp}/feipi-ppt-render.XXXXXX")"
trap 'rm -rf "$TMPDIR_RENDER"' EXIT
PROFILE_URI="$(python3 - "$TMPDIR_RENDER/profile" <<'PYPROFILE'
from pathlib import Path
import sys
print(Path(sys.argv[1]).as_uri())
PYPROFILE
)"
EXPECTED_SLIDES="$(python3 - "$INPUT_PPTX" <<'PYCOUNT'
import re
import sys
import zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    print(sum(bool(re.fullmatch(r'ppt/slides/slide[0-9]+\.xml', name)) for name in archive.namelist()))
PYCOUNT
)"
if [[ "$EXPECTED_SLIDES" -lt 1 ]]; then
  echo 'PPTX 不含可渲染页面' >&2
  exit 2
fi
if ! "${RENDER_CMD[@]}" "-env:UserInstallation=$PROFILE_URI" --convert-to pdf \
    --outdir "$TMPDIR_RENDER" "$INPUT_PPTX" > "$TMPDIR_RENDER/conversion.log" 2>&1; then
  cat "$TMPDIR_RENDER/conversion.log" >&2
  exit 2
fi
INPUT_BASE="$(basename "$INPUT_PPTX")"
PDF_FILE="$TMPDIR_RENDER/${INPUT_BASE%.*}.pdf"
if [[ ! -s "$PDF_FILE" ]]; then
  echo 'LibreOffice 未产生有效 PDF' >&2
  exit 2
fi
pdftoppm -png -r 144 "$PDF_FILE" "$TMPDIR_RENDER/slide" > "$TMPDIR_RENDER/raster.log" 2>&1
shopt -s nullglob
PNG_FILES=("$TMPDIR_RENDER"/slide-*.png)
if [[ "${#PNG_FILES[@]}" -ne "$EXPECTED_SLIDES" ]]; then
  echo "PPTX 页数与实际 PNG 数量不符：$EXPECTED_SLIDES / ${#PNG_FILES[@]}" >&2
  exit 2
fi
OUTPUT_NAMES=()
for png in "${PNG_FILES[@]}"; do
  base="${TMPDIR_RENDER##*/}-$(basename "$png")"
  cp "$png" "$OUTPUT_DIR/$base"
  OUTPUT_NAMES+=("$base")
  if [[ -z "$JSON_MODE" ]]; then echo "  已导出: $base"; fi
done
# 只登记本轮文件，输出目录里遗留的旧图不参与验收；JSON 模式 stdout 只有一份报告。
node "$SCRIPT_DIR/render_pptx.js" "$INPUT_PPTX" "$OUTPUT_DIR" "$RENDERER" "${OUTPUT_NAMES[@]}"
