# nvm 默认版本 PATH 预注入（必须在 10-ohmyzsh 之前加载）：
# 目标：让 npm -g 安装的命令在“新开终端”立即可用，不必先执行 node/npm。

# 如果外部已经设置 NVM_DIR（例如 CI 或其他脚本），这里复用外部值。
# 否则按 nvm 的默认安装目录回退。
: "${NVM_DIR:="$HOME/.nvm"}"

_nvm_read_alias() {
  local _alias_file="$1"
  local _alias_value=""

  [[ -r "$_alias_file" ]] || return 1
  _alias_value="$(<"$_alias_file")"
  _alias_value="${_alias_value//$'\r'/}"
  _alias_value="${_alias_value%%$'\n'*}"
  [[ -n "$_alias_value" ]] || return 1

  print -r -- "$_alias_value"
}

# 解析 nvm 默认版本，支持多级别名链：
# default -> lts/* -> lts/krypton -> v24.12.0
_nvm_resolve_default_version() {
  local _ref=""
  local _depth=0

  _ref="$(_nvm_read_alias "$NVM_DIR/alias/default" 2>/dev/null)" || return 1

  while (( _depth < 10 )); do
    # 匹配真实版本号（v20.19.6 / v24.12.0）。
    if [[ "$_ref" == v<->* ]]; then
      print -r -- "$_ref"
      return 0
    fi

    # 如果不是版本号，就继续按 alias/<name> 追踪下一跳。
    _ref="$(_nvm_read_alias "$NVM_DIR/alias/$_ref" 2>/dev/null)" || return 1
    _depth=$((_depth + 1))
  done

  # 防御：异常别名环路时退出，避免死循环。
  return 1
}

_nvm_default_version="$(_nvm_resolve_default_version 2>/dev/null || true)"
if [[ -n "$_nvm_default_version" ]]; then
  _nvm_default_bin="$NVM_DIR/versions/node/${_nvm_default_version}/bin"

  # 目录存在才加入 PATH，避免误配 alias/default 造成无效路径污染。
  if [[ -d "$_nvm_default_bin" ]]; then
    path_prepend "$_nvm_default_bin"
    # 与 nvm 约定保持一致，方便其他脚本直接读取当前 Node bin 目录。
    export NVM_BIN="$_nvm_default_bin"
  fi
fi

unset _nvm_default_version _nvm_default_bin
unset -f _nvm_read_alias _nvm_resolve_default_version
