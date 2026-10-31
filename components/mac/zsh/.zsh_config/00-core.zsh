# 语言与字符集
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

# 本机请求不走代理
export NO_PROXY="127.0.0.1,localhost,192.168.0.0/16"
export no_proxy="$NO_PROXY"

# PATH 工具：避免重复、避免顺序混乱（zsh 原生支持 path 数组）
typeset -U path PATH

# 将目录加到 PATH 最前面（目录存在才加）
path_prepend() { [[ -d "$1" ]] && path=("$1" $path); }

# 将目录加到 PATH 最后面（目录存在才加）
path_append() { [[ -d "$1" ]] && path=($path "$1"); }

# CLI 工具 需要打开 external editor 时的 editor选择
export VISUAL="nvim"
export EDITOR="nvim"

# 函数递归深度保护（临时安全措施）
# 防止 spaceship::includes 等函数因异常导致 infinite recursion。
# 正常 zsh 配置递归不会超过 20 层；50 留有足够余量，
# 同时能在递归异常时给出明确报错而非 segfault。
FUNCNEST=50
