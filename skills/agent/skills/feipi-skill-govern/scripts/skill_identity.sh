# Shared checks for source initialization and standalone validation.

skill_repo_root() {
  local ancestor="$1"
  while [[ "$ancestor" != / ]]; do
    if [[ -f "$ancestor/skills/registry.yaml" && -f "$ancestor/workbench" ]]; then
      printf '%s\n' "$ancestor"
      return
    fi
    ancestor="$(dirname "$ancestor")"
  done
  git rev-parse --show-toplevel 2>/dev/null || pwd -P
}

validate_skill_name() {
  local name="$1" domain action
  local segment='[a-z0-9]+(-[a-z0-9]+)*'
  if [[ ! "$name" =~ ^feipi-$segment$ || ${#name} -gt 64 || "$name" =~ (anthropic|claude) ]]; then
    echo "无效 Skill 名称：$name" >&2
    return 1
  fi
  [[ "$name" != feipi-skill-govern ]] || return 0
  local tokens=()
  IFS='-' read -r -a tokens <<< "$name"
  if [[ ${#tokens[@]} -lt 4 ]]; then
    echo "名称须符合 feipi-<domain>-<action>-<object...>：$name" >&2
    return 1
  fi
  domain="${tokens[1]}"
  action="${tokens[2]}"
  case "$domain" in
    read|write|summarize|review|analyze|test|debug|refactor|generate|gen|configure|send|plan|planning|design|build|deploy|translate|govern|code|coding|docs)
      echo "检测到旧 action-first 命名痕迹：$name" >&2
      return 1 ;;
  esac
  case "$action" in
    web|ops|automate|misc|helper|utils|tools|temp|tmp|skill)
      echo "action 不能使用低语义词：$action" >&2
      return 1 ;;
  esac
}

validate_skill_classification() {
  local part pattern='^[a-z0-9]+(-[a-z0-9]+)*$'
  for part in "$@"; do
    if [[ ! "$part" =~ $pattern ]]; then
      echo "领域或子领域应使用小写 kebab-case：$part" >&2
      return 1
    fi
    case "$part" in
      workflow|workflows|verification|maintenance|tests|evals|node_modules|__pycache__)
        echo "分类目录须表达主题：$part" >&2
        return 1 ;;
    esac
  done
}
