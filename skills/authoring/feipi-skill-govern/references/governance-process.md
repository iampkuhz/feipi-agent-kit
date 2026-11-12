# Skill 治理流程

## 适用范围

本流程只用于治理 skill 本身，不用于普通业务任务。

适用：
- 新建 skill
- 重构 skill
- 审计 skill
- 自检 `feipi-skill-govern`

不适用：
- 普通业务需求
- 没有目标 skill 的开放式”顺手都改一下”

## 阶段总览

### Step 1：基线审计

目标：
- 建立当前问题基线。
- 区分哪些是命名 / layer 问题，哪些是触发、执行、资源、脚本、验证问题。

输出：
- Step 1 基线审计文档（临时文件）

必须填写的核心字段：
- `current_name`
- `current_layer`
- `rule_violation`
- `script_localization_status`
- `validation_status`

### Step 1.5：命名与归位评审

进入条件：
- 当前名称不符合 `feipi-<domain>-<action>-<object...>`
- 当前目录未按 layer 归位
- 已有 rename 结论来自旧的 action-first 规则

输出：
- Step 1.5 rename review 文档（临时文件）
- rename plan 文档（临时文件）

必须填写的核心字段：
- `current_name`
- `target_name`
- `target_layer`
- `target_domain`
- `target_action`
- `target_object`
- `rename_reason`
- `rule_violation`

### Step 2：定点修复

目标：
- 只修改目标 skill 与直接共享文件。
- 让触发、执行、资源、脚本、验证重新对齐。

输出：
- Step 2 execution checklist（临时文件）

必须做到：
- 不无边界扩散到其他 skills
- 不继续使用旧命名真源
- 不把仓库级包装器当作唯一运行前提

### Step 3：验证与收口

目标：
- 证明这次治理不是只改文案，而是真正可运行、可验证、可追溯。

输出：
- governance report（临时文件）
- `references/reassessment-backlog.md` 中的新增待重审项

临时产物落位：
- 统一写到仓库根 `tmp/` 或系统临时目录。
- 禁止写回任意 skill 的 `assets/`、`references/`、`templates/` 或其他内部目录。
- 若需要示例文件名，优先使用 `tmp/<skill-name>-step1-audit.md`、`tmp/<skill-name>-rename-plan.md`、`tmp/<skill-name>-governance-report.md`。

## 治理产物落位与字段

### 落位规则

Step 1 基线审计、Step 1.5 rename review/rename plan、Step 2 checklist、governance report 都属于临时治理产物。
这些文件只能写到仓库根 `tmp/` 或系统临时目录，禁止提交到任意 skill 的 `assets/`、`references/`、`templates/` 或其他内部目录。

推荐命名：`tmp/<skill-name>-step1-audit.md`、`tmp/<skill-name>-rename-plan.md`、`tmp/<skill-name>-governance-report.md`。

### 通用字段

以下字段应在相关临时文档中按需出现并保持同名：
`current_name`、`target_name`、`target_layer`、`target_domain`、`target_action`、`target_object`、`rename_reason`、`rule_violation`、`script_localization_status`、`validation_status`、`current_layer`。

### 使用原则

临时文档只提供治理过程记录，不替代真实分析与验证。旧 rename 结论若不符合 v2，必须通过 Step 1.5 重审，不能直接复用历史结论。

## 暂停与重启规则

- 若治理真源发生变化，历史上尚未执行完的 Step 2C / Step 2D 一律暂停。
- 重新开始时，必须先回到 Step 1，再视情况进入 Step 1.5。
- 历史 rename plan 若基于旧规则，直接作废，不得跳过 Step 1.5 继续执行。

## 单个 skill 的标准治理顺序

1. 先读目标源码 `<target_skill>/maintenance/README.md` 与 `<target_skill>/maintenance/terminology.md`，明确业务对象、命名边界，再读当前入口文件；缺少维护资料时在本次治理中补齐。
2. 输出 Step 1 基线审计。
3. 若涉及命名或路径，输出 Step 1.5 评审与 rename plan。
4. 执行 Step 2 定点修复。
5. 执行结构校验、行为校验、旧规则残留搜索。
6. 产出 governance report，并把无关 skill 问题写入待重审清单。

## 可以保留的旧成果

- 已形成共识的 layer 分层思想。
- 中文维护要求。
- 版本与 changelog 的同日合并规则。
- “本地脚本优先，仓库级脚本仅作包装器”的方向。

## 必须重审的旧成果

- 所有基于旧 action-first 命名产出的 rename 建议。
- 所有把 `web`、`ops`、`automate` 当核心 action 的命名结论。
- 所有未经过 Step 1.5 重新评审的历史命名方案。
