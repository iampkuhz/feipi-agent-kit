# pyenv：Python 多版本管理
# 查看可以安装的版本: pyenv install --list
# 安装: pyenv install 3.XX.XX
# 切换: pyenv global 3.XX.XX
# 查看: pyenv version && python -V
export PYENV_ROOT="$HOME/.pyenv"
path_prepend "$PYENV_ROOT/bin"
path_prepend "$PYENV_ROOT/shims"

# 启动加速：不在 shell 启动阶段直接执行 `pyenv init -`（这一步通常较慢）。
# 先把 shims 放入 PATH，保证 python/pip 等命令版本解析仍然可用。
# 当你首次执行 `pyenv ...` 子命令时，再延迟初始化 pyenv 的 shell hook。
if command -v pyenv >/dev/null 2>&1; then
  _lazy_load_pyenv() {
    unset -f pyenv _lazy_load_pyenv
    eval "$(command pyenv init -)"
  }

  pyenv() {
    _lazy_load_pyenv
    pyenv "$@"
  }
fi
