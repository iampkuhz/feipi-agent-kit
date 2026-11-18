# completion 的匹配规则：大小写/下划线/点号等
zstyle ':completion:*:*' matcher-list 'm:{[:lower:]-}={[:upper:]_}' '+r:|[.]=**'

# Tab 行为：扩展或补全到最长前缀
bindkey '^I' expand-or-complete-prefix
