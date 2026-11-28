---
name: feipi-skill-govern
description: 适用于创建、重构或审计 Skill。帮助作者写清何时调用、如何执行和交付什么，并验证实际任务能否得到预期结果。
disable-model-invocation: false
icon: shield
color: purple
---

# Skill 工程治理

把用户目标落实到可核对的业务结果。结构正确、脚本退出成功和文件存在各自只证明对应的技术事实。读完本入口应能判断何时启动治理、按什么顺序执行、交付什么结果，以及何时停止或报告阻塞；细节按需读取链接规约。

## 入口与范围

- 适用于创建、重构、治理、自检 skill；普通业务执行不触发。
- 从请求确定 `target_skill`、`task_type`（create / refactor / govern / self-audit）、允许修改的直接共享文件。用户明确要求全仓时按 registry 全集分组执行；否则只处理目标，不顺手改其他 skills。
- 沿用会话中已有授权。仅要求分析或讨论时交付判断、依据与方案，不实施；已授权修改时自行完成必要调查、修复与验证。
- 先读目标源码 `<target_skill>/maintenance/README.md` 与 `<target_skill>/maintenance/terminology.md`，缺失时纳入修复；再按实际调用关系读取入口、规约、模板、脚本和消费者。

## 执行导航

1. 按 [治理流程与功能契约](references/governance-process.md) 建立需求、问题和失败案例，再审计、修复、验收。它是阶段顺序与阶段交付的唯一真源；只有涉及命名或归位才进入 Step 1.5。涉及重构时，明确新旧入口、调用者迁移、兼容方式及旧路径退出条件。
2. 需要跨阶段恢复或交接时，按 [治理记录](references/governance-artifacts.md) 保存绑定本轮输入的正式中间结果。交接实际内容或明确不足，不用文件名、目标名称或“已完成”代替结果。
3. 按 [验证与纠偏](references/workflow.md) 分别验证确定性逻辑、Agent 分析效果及真实接口链路。先定位失败所属模块，再修改及复验必要消费者。
4. 用户要求逐份人工审阅时，按 [候选界面审阅](references/manual-review.md) 展示实际候选，记录与候选绑定的确认。
5. 收口前逐项核对 [质量清单](references/quality-checklist.md)，同步版本和变更记录，交付问题、修复、验证证据、未解决项。只在需要时给出待重审项与重启建议。

## 设计边界

- 每个独立业务功能说明输入、规约、交付内容、消费者、完成条件和失败结果；简单功能可就地说明，不为凑目录拆文件。
- 新建模块或脚本前说明独立职责或真实复用场景；短小逻辑优先留在现有模块。拆分导致文件数量或维护面增长时记录必要性及实际受益者。
- 共享入口面向已加载它的执行者。宿主专用启动命令及本 Skill 自调用放在真正消费它的客户端配置或用户文档；跨 Skill 仍使用准确 ID。迁移中文按 [入口与迁移中文](references/entry-writing.md) 做上下文和语义复核。
- 总入口负责选择功能和编排调用；运行规约在对应 `references/`，源码维护入口只记录职责及依赖地图，不复制运行规则。
- `scripts/` 只放正式流程会调用、随安装提供的运行程序。仅供测试的辅助程序、生成器与 fixture 放 `tests/`；入口及脚本调用链所需资源不得藏在被打包排除的目录。确认实现确已废弃后，才连同专属测试一起删除；仍有用的测试不得为清理脚本而删。
- 校验资源归位时沿总入口、被调用脚本和引用逐层追踪：确认正式入口所需资源存在且会被打包，开发资料不会成为运行依赖。静态检查只覆盖可确定的引用事实，动态调用和语义用途须人工核对。
- 用户指出的问题成为回归案例。预期从用户需求与原始材料独立推导，核对“来源 → 功能结果 → 报告 → 用户通知”，不照抄当前实现输出作为正确答案。
- 涉及语义能力，必须检查真实 Agent 的产物与证据；单测、dry-run、关键词或中间文件存在不能替代效果评估。外部发送仍须有用户授权，未发送与未验证如实报告。
- 脚本只自动检查确定性事实，例如缺交、格式、引用、输入绑定和一致性；不让脚本冒充业务判断。

## 按需规则

| 情况 | 读取 |
|---|---|
| 命名、归类、迁移 | [命名](references/naming-conventions.md)、[主题归类](references/skill-classification.md)；按主要对象选择领域和可选子领域，另定普通命名或工作模式命名 |
| 移植外部 Skill 或更换宿主 | [依赖来源、项目 Reference、跨 Skill 调用和宿主适配](references/migration-policy.md) |
| 新建、治理历史 Skill 或修改 Description、触发和资源 | [Description、调用策略与徽章](references/frontmatter-policy.md)、[开发资料与安装边界](references/development-layout.md)、[仓库约束](references/repo-constraints.md) |
| 排查文本开销、跨文档重复或精简后的行为变化 | [文本 Token 对比与查重](references/workflow.md#文本-token-对比) |
| 新增 Skill、补齐图标、换图或发现新版 Cursor 图标 | [查找、设计与分发 Skill 图标](references/skill-icons.md)。实现时先从用途检索，再选择复用或新绘，绑定后验证 |
| 更新收口 | [版本与变更记录](references/version-changelog-policy.md)；同日同 skill 只升版一次、合并一条摘要 |
| 历史规则冲突 | [反模式](references/anti-patterns.md)、[待重审清单](references/reassessment-backlog.md)；旧 action-first 结论重新评审 |

## 本地工具

以下命令从治理 Skill 源码目录执行；在仓库根执行时加 skill 路径前缀。安装后的运行脚本不依赖源码测试，`tests/run.sh` 仅用于源码自测。仓库级包装器不能成为唯一入口。

```bash
bash scripts/init_skill.sh report-generate-brief --domain content --target "$target_root"
bash scripts/validate.sh "$target_skill" --require-maintenance
python3 scripts/check_portability.py "$target_skill"
python3 scripts/skill_icon_catalog.py search --skill "$target_skill"
bash tests/run.sh
```

- `init_skill.sh` 生成待完善的脚手架，不代表业务功能已可用。
- 初始化为普通 Skill 配置自动匹配，为工作模式配置显式调用，并生成默认颜色和图标资源。其他资源目录在有文件或调用方明确指定时创建。
- `validate.sh` 校验结构、双端调用策略、徽章及图标资源；`check_portability.py` 静态扫描脚本和测试，不能证明已在双平台实测。
- `tests/run.sh` 是治理 Skill 的确定性回归入口。治理目标的行为评估按其实际能力设计，不能用治理自测替代。
- `scripts/check_delivery.py` 按治理记录契约检查交接完整性；只报告技术检查结果。

## 跨平台与分发

- 审核所有实际读、写和执行路径。优先使用相对于 Skill、仓库或任务目录的路径，按 [运行路径兼容](references/workflow.md#运行路径兼容) 核对运行时解析和安装后可用性。运行资源禁止依赖固定机器路径或 IDE 私有目录。
- 临时产物写到唯一的仓库 `tmp/` 子目录或系统临时目录，只清理本次创建的路径。
- 安装、校验兼容 macOS Bash 3.2/BSD 与 Linux Bash/GNU；外部依赖先探测，不隐式依赖 `rg`。未实测的平台单列。
- 运行知识保留在 `references/`；普通 skill 运行内容不依赖源码维护资料、测试或评估目录。创建和治理时按需读取目标 `tests/`、`evals/`，安装时递归排除开发资料。
- 中文维护，保留必要技术名称。临时治理报告和评估运行产物不写回 skill 源码。
