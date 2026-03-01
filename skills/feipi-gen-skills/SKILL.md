---
name: feipi-gen-skills
description: 用于在本仓库创建、更新与重构中文 skills，覆盖结构设计、文案完善、脚本补齐与验证闭环。在新建 skill、统一规范或批量提升已有 skill 质量时使用。
---

# Skill Creator（中文）

## 核心目标

以最小上下文成本，产出可发现、可执行、可验证、可迭代的高质量 skills。

## 仓库落地硬约束（创建/更新 skill 必须满足）

1. 命名约束
- skill 目录名必须匹配：`^[a-z0-9-]{1,64}$`。

2. 中文维护约束
- `SKILL.md` 的 `description` 与正文使用中文。
- `agents/openai.yaml` 的 `display_name`、`short_description`、`default_prompt` 使用中文。
- `references/` 默认中文（如保留英文原文，需附中文摘要）。
- 脚本与配置注释统一中文。

3. 测试结构约束（开发流程）
- 每个 skill 必须提供统一测试入口：`<skill-root>/<name>/scripts/test.sh`。
- 每个 skill 的测试数据默认放在：`<skill-root>/<name>/references/test_cases.txt`。
- 仓库级统一通过 `make test SKILL=<name>` 调度，不依赖非标准脚本名（支持 `skills/` 与 `.agents/skills/`）。
- 上述测试命令仅在创建/修改 skill 的开发流程执行，不写入目标 skill 的 `SKILL.md`。

4. 校验约束
- 新建或修改 skill 后，必须执行：`make validate DIR=<skill-root>/<name>`。

5. 新建 skill 目录判定约束
- 若用户明确要求“在本仓库内创建新 skill”，目标根目录固定为 `.agents/skills/`。
- 若用户未特别说明，且当前仓库存在 `skills/` 目录，默认根目录为 `skills/`。
- 若用户未特别说明且当前仓库不存在 `skills/` 目录，默认回退到 `.agents/skills/`。
- 开发阶段可使用 `make new SKILL=<name> TARGET=repo|skills|auto` 显式对齐目录策略。


## 目录标准

每个 skill 推荐结构：

```txt
<skill-name>/
├── SKILL.md
├── agents/openai.yaml
├── scripts/
├── references/
└── assets/
```

说明：
- `SKILL.md`：唯一必需文件，定义触发与执行规则。
- `agents/openai.yaml`：UI 元数据（展示名、短描述、默认提示词）。
- `scripts/`：确定性、可重复执行的脚本。
- `references/`：按需加载的详细资料。
- `assets/`：输出时使用的模板或静态文件。

## 强约束原则

1. 简洁优先
- SKILL.md 只保留高价值信息；默认假设模型已具备通用知识。
- 正文建议 <= 500 行；超出即拆分到 `references/`。

2. 验证优先
- 先定义验收标准，再实现内容。
- 无可执行验证证据视为未完成。

3. 自由度匹配风险
- 高自由度：多方案均可行的分析类任务。
- 中自由度：有推荐模式、可参数化任务。
- 低自由度：高风险、易错、必须按序执行任务。

4. 渐进式披露
- SKILL.md 提供导航与流程。
- 细节放 `references/` 并由 SKILL.md 直接一跳链接。
- 避免多层嵌套引用。

5. 中文维护
- 面向维护者字段使用中文：`description`、正文、`agents/openai.yaml` 关键字段。

6. 环境变量最小化
- 默认不新增环境变量；能用脚本内常量、自动探测或命令参数解决的，不得引入环境变量。
- 必须遵循“尽可能不加环境变量”：默认方案中不推荐通过新增环境变量来控制行为。
- 在 `SKILL.md`、脚本报错文案、测试说明中，禁止把“新增环境变量控制”作为首选建议；仅在凭据/密钥等外部敏感配置场景可例外。
- 若确实无法避免，才允许新增少量环境变量，且优先 0~1 个。
- 环境变量命名使用业务语义，避免工具绑定前缀（如优先 `AGENT_*`，避免 `YTDLP_*`）。
- 所有可调参数必须集中放在脚本顶部“可调参数区”，并配中文注释说明用途与修改方式。
- 每次新增/修改环境变量时，必须同步更新仓库根目录 `.env.example` 与对应 `SKILL.md` 的参数说明。
- 仓库内禁止新增分散的 `references/.env.example`；环境变量模板只维护一份，并在变量注释中标注使用 skill。
- 所有 skill 禁止读取或加载 skill 子目录内的 `.env`；只读取当前 shell 环境变量。
- 是否将 `~/.env` 注入到上下文由 `zsh` 或用户命令负责，skill 与脚本不做加载与兜底。
- 场景相同的变量必须统一命名，且每次优化默认所有环境适配最新版，不做新旧兼容读取。
- PlantUML 端口只保留 `AGENT_PLANTUML_PORT`，禁止同时支持 `AGENT_PLANTUML_SERVER_PORT`。
- 视频类 cookie 按站点区分变量名：`AGENT_YOUTUBE_COOKIE_FILE`、`AGENT_BILIBILI_COOKIE_FILE`，不使用通用 `AGENT_VIDEO_COOKIE_FILE`。
- 新增/调整统一命名时，仅以最新命名为准并同步更新根 `.env.example`，不保留旧名映射，不做兼容读取。

7. 版本兼容策略
- 每次优化/重构默认所有环境适配最新版，不保留旧版兼容路径或多套读写逻辑。


## Frontmatter 规范

1. 仅保留 `name` 与 `description`。
2. `name`：
- 与目录名一致。
- 匹配 `^[a-z0-9-]{1,64}$`。
- 不含保留词 `anthropic`、`claude`。
- 不含 XML 标签。
3. `description`：
- 非空，<= 1024 字符。
- 使用第三人称，写清“做什么 + 什么时候用”。
- 不含 XML 标签。

## 命名规范

强制格式：`feipi-<action>-<target...>`。
- 示例：`feipi-coding-react-components`、`feipi-gen-api-tests`、`feipi-read-video-transcript`
- `action` 必须来自标准动作字典
- 详细规则见：`references/naming-conventions.md`

## 四阶段工作流（Explore -> Plan -> Implement -> Verify）

1. Explore（探索）
- 收集任务目标、输入输出、边界与风险。
- 只读必要文件；先索引后定向打开。

2. Plan（规划）
- 明确改动文件、理由、验证方法。
- 变更可一句话描述 diff 时可直做，不做重规划。

3. Implement（实现）
- 先落可复用资源（脚本/参考/资产），再完善 SKILL.md。
- 对确定性操作优先写脚本并执行脚本，而不是临时重写代码。
- 避免 Windows 路径，统一正斜杠。

4. Verify（验证）
- 运行仓库校验：`make validate DIR=<skill-root>/<name>`。
- 执行至少一种任务级验证（测试、命令、截图比对、结构校验）。
- 交付必须给出：验证步骤、结果、剩余风险。

## 使用态与开发流程分离（强约束）

1. 使用态（调用 skill 完成用户任务）
- `SKILL.md` 只保留完成任务所需信息（输入、输出、执行步骤、结果校验）。
- 禁止在非 `feipi-gen-skills` 的 `SKILL.md` 中出现仓库维护命令（如 `make test SKILL=...`、`make validate DIR=...`）。

2. 开发流程（创建/修改/重构 skill）
- 在开发阶段执行 `make validate DIR=<skill-root>/<name>` 与必要的 `make test SKILL=<name>`。
- 开发校验结果记录在开发过程与提交说明中，不沉淀到目标 skill 的 `SKILL.md`。

## 变更记录与文档同步（开发流程）

1. 每次更新完成后，必须更新仓库根目录 `CHANGELOG.md`。
- 按天分章节，格式 `## YYYY-MM-DD`，时间倒序排列（新日期在上）。
- 记录当次更新的最小要点，避免冗长。
- 更新前先检查今天章节是否已有相同记录，已有则不重复追加。
- 若是继续优化昨天的内容，在昨天对应条目追加“未调试成功”标记；最多只回看一天，更早内容不做修改。

2. 每次更新后，检查 `README.md` 是否需要微调（命令、示例、路径等变更）。

## 反馈循环

默认采用循环：验证 -> 修复 -> 再验证。

若任务高风险（批量改动、破坏性操作、复杂规则）：
1. 先生成中间计划文件（如 `changes.json`）。
2. 用脚本校验计划。
3. 通过后再执行变更。

## 反模式与修复

1. 说明冗长且重复常识
- 修复：删解释，保留流程、约束、命令与示例。

2. 给太多并列方案导致选择困难
- 修复：给一个默认方案 + 一个例外逃生舱。

3. 只给规则，不给验证
- 修复：补充可执行验证步骤与通过条件。

4. 路径/目录组织混乱
- 修复：用语义化文件名，按领域拆分 `references/`。

5. 过度依赖环境变量控制
- 修复：优先改为脚本常量或自动探测；仅在必须使用外部凭据时保留最少环境变量。

## 测试与迭代要求

1. 至少准备 3 个评估场景（正常、边界、异常）。
2. 优先真实任务回放，不只做静态阅读。
3. 若目标环境涉及多模型，至少在预期模型档位做一次对照测试。
4. 根据观察到的失败行为迭代，不基于猜测优化。

## 交付清单

每次创建/更新 skill 前，复制并打勾：

```txt
技能质量清单
- [ ] frontmatter 合规（name/description）
- [ ] description 清晰说明能力与触发时机
- [ ] SKILL.md 正文 <= 500 行
- [ ] 新建 skill 时目录判定符合规则（本仓库内 -> `.agents/skills/`；默认优先 `skills/`）
- [ ] 已提供验证步骤与通过标准
- [ ] 已运行 make validate
- [ ] 非 `feipi-gen-skills` 的 `SKILL.md` 不含 `make test SKILL=...` / `make validate DIR=...`
- [ ] 已更新 `CHANGELOG.md`（按天倒序、避免重复、必要时标记昨天未调试成功）
- [ ] 已检查 `README.md` 是否需要微调
- [ ] 无 skill 内分散 `.env.example`（统一维护于仓库根 `.env.example`）
- [ ] 不加载任何 `.env` 文件（只读取当前 shell 环境变量）
- [ ] 同类场景环境变量命名一致（仅最新命名，不保留兼容旧名）
- [ ] 文件引用均为一级深链接
- [ ] 无 Windows 风格路径
- [ ] 术语一致，示例可执行
```
