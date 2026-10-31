# OPENSPEC:START
# OpenSpec-cn shell 补全配置：仅设置 fpath，不调用 compinit。
# compinit 由 oh-my-zsh 统一初始化，避免重复调用导致 .zcompdump 和 bad file descriptor。
# 注意：此文件编号为 05，必须在 10-ohmyzsh.zsh 之前加载，否则 fpath 不生效。
fpath=("$HOME/.oh-my-zsh/custom/completions" $fpath)
# OPENSPEC:END

# OpenClaw Completion
_openclaw_completion="$HOME/.openclaw/completions/openclaw.zsh"
if [[ -r "$_openclaw_completion" ]]; then
  source "$_openclaw_completion"
fi
unset _openclaw_completion
