---
name: feipi-skill-govern
description: 用于创建、重构或审计 skill，建立功能交付契约并验证用户目标是否实现，同时治理命名、触发、资源与脚本边界；普通业务执行不使用。
---

# Skill 工程治理

把用户目标落实到可核对的业务结果。结构正确、脚本退出成功和文件存在各自只证明对应的技术事实。

## 入口与范围

- 适用于创建、重构、治理、自检 skill；普通业务执行不触发。
- 从请求确定 `target_skill`、`task_type`（create / refactor / govern / self-audit）、允许修改的直接共享文件。用户明确要求全仓时按 registry 全集分组执行；否则只处理目标，不顺手改其他 skills。
- 沿用会话中已有授权。仅要求分析或讨论时交付判断、依据与方案，不实施；已授权修改时自行完成必要调查、修复与验证。
- 先读目标源码 `<target_skill>/maintenance/README.md` 与 `<target_skill>/maintenance/terminology.md`，缺失时纳入修复；再按实际调用关系读取入口、规约、模板、脚本和消费者。

## 执行导航

1. 按 [治理流程与功能契约](references/governance-process.md) 建立需求、问题和失败案例，再审计、修复、验收。它是阶段顺序与阶段交付的唯一真源；只有涉及命名或归位才进入 Step 1.5。
2. 需要跨阶段恢复或交接时，按 [治理记录](references/governance-artifacts.md) 保存绑定本轮输入的正式中间结果。交接实际内容或明确不足，不用文件名、目标名称或“已完成”代替结果。
3. 按 [验证与纠偏](references/workflow.md) 分别验证确定性逻辑、Agent 分析效果及真实接口链路。先定位失败所属模块，再修改及复验必要消费者。
4. 收口前逐项核对 [质量清单](references/quality-checklist.md)，同步版本和变更记录，交付问题、修复、验证证据、未解决项。只在需要时给出待重审项与重启建议。

## 设计边界

- 每个独立业务功能说明输入、规约、交付内容、消费者、完成条件和失败结果；简单功能可就地说明，不为凑目录拆文件。
- 总入口负责选择功能和编排调用；运行规约在对应 `references/`，源码维护入口只记录职责及依赖地图，不复制运行规则。
- 用户指出的问题成为回归案例。预期从用户需求与原始材料独立推导，核对“来源 → 功能结果 → 报告 → 用户通知”，不照抄当前实现输出作为正确答案。
- 涉及语义能力，必须检查真实 Agent 的产物与证据；单测、dry-run、关键词或中间文件存在不能替代效果评估。外部发送仍须有用户授权，未发送与未验证如实报告。
- 脚本只自动检查确定性事实，例如缺交、格式、引用、输入绑定和一致性；不让脚本冒充业务判断。

## 按需规则

| 情况 | 读取 |
|---|---|
| 命名、layer、迁移 | [命名](references/naming-conventions.md)、[分层](references/skill-layering-policy.md)；命名按 domain → action → object → layer，`feipi-skill-govern` 为保留特例 |
| 新建或修改资源布局 | [开发资料与安装边界](references/development-layout.md)、[仓库约束](references/repo-constraints.md)、[frontmatter](references/frontmatter-policy.md) |
| 更新收口 | [版本与变更记录](references/version-changelog-policy.md)；同日同 skill 只升版一次、合并一条摘要 |
| 历史规则冲突 | [反模式](references/anti-patterns.md)、[待重审清单](references/reassessment-backlog.md)；旧 action-first 结论重新评审 |

## 本地工具

以下命令从治理 Skill 源码目录执行；在仓库根执行时加 skill 路径前缀。安装后的运行脚本不依赖源码测试，`tests/run.sh` 仅用于源码自测。仓库级包装器不能成为唯一入口。

```bash
bash scripts/init_skill.sh report-generate-brief --layer authoring --target "$target_root"
bash scripts/validate.sh "$target_skill" --require-maintenance
python3 scripts/check_portability.py "$target_skill"
bash tests/run.sh
```

- `init_skill.sh` 生成待完善的脚手架，不代表业务功能已可用。
- `validate.sh` 是结构校验；`check_portability.py` 静态扫描脚本和测试，不能证明已在双平台实测。
- `tests/run.sh` 是治理 Skill 的确定性回归入口。治理目标的行为评估按其实际能力设计，不能用治理自测替代。
- `scripts/check_delivery.py` 按治理记录契约检查交接完整性；只报告技术检查结果。

## 跨平台与分发

- 路径从脚本位置、显式参数或系统接口推导，不写开发者机器绝对路径；临时产物写到唯一的仓库 `tmp/` 子目录或系统临时目录，只清理本次创建的路径。
- 安装、校验兼容 macOS Bash 3.2/BSD 与 Linux Bash/GNU；外部依赖先探测，不隐式依赖 `rg`。未实测的平台单列。
- 运行知识保留在 `references/`；普通 skill 运行内容不依赖源码维护资料、测试或评估目录。创建和治理时按需读取目标 `tests/`、`evals/`，安装时递归排除开发资料。
- 中文维护，保留必要技术名称。临时治理报告和评估运行产物不写回 skill 源码。
