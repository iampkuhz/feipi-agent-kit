# rbenv：Ruby 多版本管理（仅在交互模式加载更合理）
if command -v rbenv >/dev/null 2>&1; then
  eval "$(rbenv init - zsh)"
fi
