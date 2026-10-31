# nvm：Node 多版本管理
# 启动加速策略：zsh 启动时不立即 source nvm.sh，而是在首次用到 nvm/node/npm/npx 时再加载。
: "${NVM_DIR:="$HOME/.nvm"}"

# 每个 wrapper 自包含 lazy-load 逻辑，不依赖任何外部函数。
# 这样在 Claude Code shell snapshot 恢复时也不会因缺失 helper 函数而报错。
# 必须先删除占位函数再加载 nvm.sh，不能删除加载后生成的真实 nvm 函数。
nvm() {
  unset -f nvm node npm npx
  if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
    print -u2 "nvm 尚未安装；请运行 bash bootstrap/node.sh install。"
    return 127
  fi
  source "$NVM_DIR/nvm.sh" || return
  nvm "$@"
}
node() {
  unset -f nvm node npm npx
  # 无 nvm 时沿用系统 Node；有 nvm 时加载其默认版本。
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    source "$NVM_DIR/nvm.sh" || return
  fi
  node "$@"
}
npm() {
  unset -f nvm node npm npx
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    source "$NVM_DIR/nvm.sh" || return
  fi
  npm "$@"
}
npx() {
  unset -f nvm node npm npx
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    source "$NVM_DIR/nvm.sh" || return
  fi
  npx "$@"
}

# Grammarly LSP 在 Node v24 下偶发 wasm 路径解析报错。
# 启动加速：这里不调用 `nvm which`，直接按目录优先探测 v20，再探测 v22。
if [[ -z "${GRAMMARLY_NODE_PATH:-}" ]]; then
  _grammarly_node_path=""

  for _node_candidate in "$NVM_DIR"/versions/node/v20*/bin/node(N) "$NVM_DIR"/versions/node/v22*/bin/node(N); do
    if [[ -x "$_node_candidate" ]]; then
      _grammarly_node_path="$_node_candidate"
      break
    fi
  done

  if [[ -n "$_grammarly_node_path" ]]; then
    export GRAMMARLY_NODE_PATH="$_grammarly_node_path"
  fi

  unset _grammarly_node_path _node_candidate
fi
