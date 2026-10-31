#!/usr/bin/env bash
# 由 ohmyzsh.sh 和离线测试加载；本文件自身不生成补全或修改环境。

write_completion_cache() (
  # 子 shell 隔离清理 trap；目标旁的临时文件保证最终替换不跨文件系统。
  local target="$1" temporary="" error_log="" status=0
  shift
  trap '[[ -z "$temporary" ]] || rm -f -- "$temporary"; [[ -z "$error_log" ]] || rm -f -- "$error_log"' EXIT
  if [[ -L "$target" || (-e "$target" && ! -f "$target") ]]; then
    echo "补全更新跳过：目标不是普通缓存文件，未接管 $target" >&2
    return 1
  fi
  temporary="$(mktemp "${target}.tmp.XXXXXXXX")" || return 1
  error_log="$(mktemp "${target}.err.XXXXXXXX")" || return 1
  # 即使生成了一半才失败，也只污染临时文件；不再用 || true 吞掉失败。
  "$@" >"$temporary" 2>"$error_log" || status=$?
  if [[ "$status" != 0 || ! -s "$temporary" ]]; then
    echo "补全更新失败：$target（退出码 $status，或输出为空）；原缓存保留。" >&2
    return 1
  fi
  # -f 禁用用户启动文件，-n 仅解析语法；不加载生成的补全函数。
  if ! zsh -f -n "$temporary" 2>"$error_log"; then
    echo "补全语法检查失败：$target；原缓存保留。" >&2
    return 1
  fi
  if [[ -L "$target" || (-e "$target" && ! -f "$target") ]]; then
    echo "补全目标类型已变化：$target；未替换。" >&2
    return 1
  fi
  mv -f -- "$temporary" "$target" || return 1
)
