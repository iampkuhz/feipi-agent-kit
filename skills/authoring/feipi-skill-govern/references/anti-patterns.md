# 反模式与修复

## 继续传播 action-first 命名

**症状**：文档、脚本或模板仍写旧 action-first 命名文本，或默认先挑 action 再补对象。

**修复**：统一改回 `feipi-<domain>-<action>-<object...>`，命名决策顺序固定为 `domain -> action -> object -> layer`。

## 把 layer 混进 skill 主语法

**症状**：名称里出现 `integration`、`platform` 等层名，或者先定 layer 再倒推 domain。

**修复**：把 layer 还原成目录归位决策，名称只表达 domain、action、object。

## 用低语义 action 兜底

**症状**：默认推荐 `web`、`ops`、`automate` 之类词当 action。

**修复**：回到任务本身，选择真正可执行的动词原形，如 `send`、`configure`、`read`、`generate`。

## 把治理 skill 当业务 skill

**症状**：`feipi-skill-govern` 的触发条件写得像普通业务执行器，导致误触发。

**修复**：明确声明它只处理 skill 创建、重构、治理、自检，不执行普通业务任务。

## 只改目标 skill，顺手扩散到其他 skills

**症状**：发现仓库里还有其他问题，就顺手一起改名、补脚本。

**修复**：默认只改目标 skill 与直接共享文件；其他问题写入待重审清单。

## 仍把仓库级 make 当唯一真入口

**症状**：文档或模板只写 `make new`、`make test`，本地 `init / validate / test` 不完整。

**修复**：以当前 skill 本地脚本为主入口，`make` 仅作包装器。

## 校验只看文本，不看行为

**症状**：只用 `grep` 搜关键词，无法证明脚本、模板、初始化流程真的能跑。

**修复**：按 `workflow.md` 区分技术、语义和链路证据。初始化临时 Skill 只能证明脚手架能生成；涉及分析效果时，审阅真实 Agent 的实际产物及来源。

## 把目标名保留当作业务内容完整

**症状**：测试只检查 Skill 名称或问题 ID，报告没有具体问题和未解决原因；测试与实现一同漏项。

**修复**：从原始需求独立制定预期，逐项追踪来源、功能结果、报告及用户通知中的实际内容，加入遗漏和部分失败案例。

## 用总入口提示词修补所有失败

**症状**：材料、Agent、脚本或展示发生问题，都向 SKILL.md 追加规则；维护资料也重复运行规则。

**修复**：定位首次失败环节，在所属功能规约、实现及必要消费者处修复。入口只编排，维护资料只指向职责真源。

## 历史 rename 结论未经重审直接继续执行

**症状**：Step 2C / Step 2D 继续沿用旧规则产出的 rename plan。

**修复**：暂停后续步骤，回到 Step 1 和 Step 1.5 重新审计与评审。

## 把临时治理文档提交进 skill

**症状**：Step 1 基线审计、Step 1.5 rename review、Step 2 checklist、governance report 或 anti-pattern 草稿出现在 skill 的 `assets/`、`references/`、`templates/` 内。

**修复**：把这类文档移到仓库根 `tmp/` 或系统临时目录；skill 内只保留长期规则、脚本和可复用模板。
