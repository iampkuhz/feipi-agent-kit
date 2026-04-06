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

**症状**：发现仓库里还有其他问题，就顺手一起改名、迁移、补脚本。

**修复**：默认只改目标 skill 与直接共享文件；其他问题写入待重审清单。

## 仍把仓库级 make 当唯一真入口

**症状**：文档或模板只写 `make new`、`make test`，本地 `init / validate / test` 不完整。

**修复**：以当前 skill 本地脚本为主入口，`make` 仅作包装器。

## 校验只看文本，不看行为

**症状**：只用 `grep` 搜关键词，无法证明脚本、模板、初始化流程真的能跑。

**修复**：补真实动作验证，如初始化临时 skill、执行本地测试、验证失败路径。

## 历史 rename 结论未经重审直接继续执行

**症状**：Step 2C / Step 2D 继续沿用旧规则产出的 rename plan。

**修复**：暂停后续迁移，回到 Step 1 和 Step 1.5 重新审计与评审。
