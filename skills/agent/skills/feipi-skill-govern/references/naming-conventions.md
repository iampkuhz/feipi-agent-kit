# Skill 命名规范

## 唯一真源

普通 Skill 使用：

```txt
feipi-<domain>-<action>-<object...>
```

保留 `feipi-skill-govern` 的历史特例和本版搬迁 Skill 的实际调用 ID。新建时使用现行规则，已有调用者不因目录调整而改名。

显式进入、约束当前会话协作并根据任务选择内部路线的工作模式使用 `feipi-<领域>-<模式名>-mode`。例如 `feipi-engineering-feiteto-mode`。模式名称标识可辨识的协作方式。普通 Skill 继续使用动作与对象命名。

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

治理前先读目标源码 `<target_skill>/maintenance/README.md` 与 `<target_skill>/maintenance/terminology.md`，确定业务对象与命名边界；缺少时在本次治理中补齐。

先按 [主题归类](skill-classification.md) 判断主要对象和存放位置，再按以下顺序选择普通 Skill ID：

1. 先定 `domain`
2. 再定 `action`
3. 再定 `object`

说明：
- 源码分类和 Skill 名称分别验证。已有 ID 不随源码路径变化。
- 若 `domain` 还没想清楚，不要先用一个宽泛 action 抢占名称。

## 强制约束

- 全小写。
- kebab-case。
- 仅允许字母、数字、连字符。
- 总长度建议不超过 64。
- 名称要兼顾可读性、可区分性、可治理性。
- 尽量避免无意义缩写；若必须缩写，需是团队已有稳定术语。

## 规约与辅助脚本

- 规约可以使用 `rules`；人工或 Agent 按明确标准审阅业务对象时可使用 `review`。
- 确定性辅助脚本按 `fetch`、`get`、`parse`、`compare`、`validate`、`save`、`render` 等具体操作命名，不暗示脚本会智能理解、判断或决策。
- 避免重复父目录或 Skill 已表达的前缀；维护术语表说明实际业务对象与边界。
- 保留现有兼容接口，不为风格统一批量重命名。

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
- `feipi-openclaw-configure-runtime`
- `feipi-video-summarize-url`

## domain 选择规则

- domain 应优先表达能力域、工具域、平台域或集成对象，而不是目录层名。
- 领域用具体业务或能力表达。子领域由源码路径体现。

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
- `feipi-plantuml-generate-diagram`
- `feipi-openclaw-configure-runtime`
- `feipi-report-generate-brief`

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
- [ ] 已核对源码主题归类和现有调用 ID
- [ ] 目标名符合 feipi-<domain>-<action>-<object...>
- [ ] action 是动词原形，不是 web/ops/automate 等低语义词
- [ ] 未与现有 skill 语义重复
- [ ] 已在 Step 1.5 记录 rename_reason、rule_violation
```
