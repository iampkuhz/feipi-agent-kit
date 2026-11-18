# Zsh 启动入口。私有环境变量取自本机，公开配置按编号加载。
if [[ -r "$HOME/.env" ]]; then
  set -a
  source "$HOME/.env"
  set +a
fi

# :a 保留 Stow 入口所在目录，正常启动从 HOME 读取各模块，源码调试从检出目录读取。
for _feipi_module in "${${(%):-%N}:a:h}/.zsh_config"/*.zsh(N); do
  source "$_feipi_module"
done
unset _feipi_module
