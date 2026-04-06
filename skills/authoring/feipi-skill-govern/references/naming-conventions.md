# Skill 命名规范 v2

## 唯一真源

除保留特例 `feipi-skill-govern` 外，仓库内 skill 名统一使用：

```txt
feipi-<domain>-<action>-<object...>
```

这是当前唯一有效的主语法；历史上的 action-first 命名文本与旧四段变体均不再作为现行规则文本使用。

## 四段含义

1. `feipi`
- 固定前缀，用于仓库内唯一识别。

2. `domain`
- 能力域、工具域、集成域或场景域。
- 目标是先说明“在哪个能力上下文里做事”，例如 `video`、`plantuml`、`dingtalk`、`openclaw`。

3. `action`
- 动词原形，说明 skill 的核心动作。
- 应优先选择可执行、可验证的动作词，例如 `read`、`generate`、`summarize`、`configure`、`send`、`review`。

4. `object`
- 对象、载体或产物。
- 用来说明 action 作用在什么上，例如 `youtube`、`webhook`、`architecture-diagram`、`innovation-disclosure`。

## 命名决策顺序

命名时严格按以下顺序判断，不要倒推：

1. 先定 `domain`
2. 再定 `action`
3. 再定 `object`
4. 最后定 `layer`

说明：
- layer 是目录归位决策，不参与主名称拼装。
- 若 `domain` 还没想清楚，不要先用一个宽泛 action 抢占名称。

## 强制约束

- 全小写。
- kebab-case。
- 仅允许字母、数字、连字符。
- 总长度建议不超过 64。
- 名称要兼顾可读性、可区分性、可治理性。
- 尽量避免无意义缩写；若必须缩写，需是团队已有稳定术语。

## action 选择规则

- action 必须是动词原形。
- action 应表达稳定主动作，而不是技术栈、渠道或泛化标签。
- 不把 `web`、`ops`、`automate`、`misc`、`helper`、`utils` 当默认 action 推荐。
- 若第二段本身已经像 `read`、`generate`、`summarize` 这类动词，通常说明你把旧 action-first 命名直接搬过来了，应先回到 domain 重新命名。
- 若动作不清晰，先回到任务本身，明确“它到底在做什么”。

反例：
- `feipi-dingtalk-web-webhook`
- `feipi-openclaw-ops-config`
- `feipi-video-automate-summary`

更合理的命名方向：
- `feipi-dingtalk-send-webhook`
- `feipi-openclaw-configure-runtime`
- `feipi-video-summarize-url`

## domain 选择规则

- domain 应优先表达能力域、工具域、平台域或集成对象，而不是目录层名。
- 不要为了迁就 layer 直接把 `integration`、`platform`、`authoring` 写进 skill 名。
- 若 layer 与 domain 重复，优先保留更具体的 domain。

反例：
- `feipi-integration-read-youtube`
- `feipi-platform-configure-openclaw`

更合理的命名方向：
- `feipi-video-read-youtube`
- `feipi-openclaw-configure-runtime`

## object 选择规则

- object 必须落到对象、载体或产物，而不是空泛尾巴。
- 优先用 1 到 3 段描述对象，避免过长尾串。
- object 若天然是复合词，使用 kebab-case 拆开。

## 推荐示例

- `feipi-video-read-youtube`
- `feipi-video-read-bilibili`
- `feipi-video-read-url`
- `feipi-video-summarize-url`
- `feipi-plantuml-generate-architecture-diagram`
- `feipi-plantuml-generate-sequence-diagram`
- `feipi-dingtalk-send-webhook`
- `feipi-openclaw-configure-runtime`
- `feipi-patent-generate-innovation-disclosure`

## 禁止示例

- `feipi-read-youtube-video`
- `feipi-gen-plantuml-architecture-diagram`
- `feipi-ops-openclaw-config`
- `feipi-web-dingtalk-webhook`
- `helper`、`utils`、`misc`、`tmp-fix`

## 新建或重命名前检查清单

```txt
命名检查
- [ ] 已先确定 target_domain
- [ ] 已先确定 target_action
- [ ] 已先确定 target_object
- [ ] 已确认 target_layer 只用于目录，不进入 skill 主语法
- [ ] 目标名符合 feipi-<domain>-<action>-<object...>
- [ ] action 是动词原形，不是 web/ops/automate 等低语义词
- [ ] 未与现有 skill 语义重复
- [ ] 已在 Step 1.5 记录 rename_reason、rule_violation、migration_risk
```
