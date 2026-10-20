# 文本精炼评估数据

本目录供 skill 维护与评估使用，不进入日常改写上下文，也不随 skill 安装。

## 真实文档样例

| 用例 | 原文快照 | 参考交付（正文与问题清单） | 应包括与不应包括 | 来源 |
|------|----------|----------|------------------|------|
| 文档整理进展汇报 | [input.md](documents/lexiflow-documentation-report/input.md) | [reference.md](documents/lexiflow-documentation-report/reference.md) | [expectations.json](documents/lexiflow-documentation-report/expectations.json) | `lexiflow/docs/roadmap/master-plan/phase2/status.md`，46–61 行：文档整理与验证边界 |
| 当前交付状态汇报 | [input.md](documents/lexiflow-delivery-status/input.md) | [reference.md](documents/lexiflow-delivery-status/reference.md) | [expectations.json](documents/lexiflow-delivery-status/expectations.json) | 同一状态页，1–17 行：已有实现及当前未完成项 |
| 产品说明与误报控制 | [input.md](documents/lexiflow-product-scope/input.md) | [reference.md](documents/lexiflow-product-scope/reference.md) | [expectations.json](documents/lexiflow-product-scope/expectations.json) | `lexiflow/docs/system/experience.md`，全文 33 行 |

用户已明确指定使用 `lexiflow/docs`。三组原文均从该目录已有文档逐行复制，未添加测试所需的虚构事实；LexiFlow 源文件保持原样。此前暂选的其他项目文档已从现行用例中替换，旧执行记录只保留在 `tmp/`，不作为这三组用例的通过证据。

每组 `provenance.json` 记录来源项目、路径、文件提交、截取范围及完整源文件和快照的 SHA-256。状态页对应 2026-10-11 文件版本，产品说明对应 2026-10-10 文件版本；均在 2026-10-16 采样，采样时所选文件无未提交修改。输入快照独立保存，运行评估无需访问来源项目，也无需打开原文引用的链接；相对链接仍保留其来源文档中的目标。

**来源目录已确认，具体节选、参考稿及验收项仍待用户审核。** 文档整理样例直接包含此前协作记录的“用户要求—当前实现”，可据此核对已有约定；它不能证明本次新稿已获认可。两份汇报参考稿展示一种整理方法；产品说明参考稿只调整一处搭配，测试成熟文稿中的局部问题识别与误报控制，不预设问题数量。后续确认时只更新有真实依据的确认状态，不补写历史认可记录。

## 协作约定与具体验收

当前用户明确要求：

- “把无效的过渡、历史讨论的黑话屏蔽掉。”
- “这个 skill 第一个要处理的就是汇报文档的去废话、去 ai 味儿。”
- “一定要添加测试数据。把本地之前整理的文档作为样例……应该包括什么、应该不包括什么。”
- “区分发现问题和修复问题……也要提供之前的问题点 list，方便主 agent 自行分析，看下要不要自己二次优化。”
- 本地历史样例来自“lexiflow 里面的 docs”。

据此形成以下验收方向；具体事实清单由原文推导，见各组 `expectations.json`，仍可在审阅参考稿时调整。

| 应包括 | 不应包括 |
|--------|----------|
| 汇报对象、核心结论，以及理解结论需要的机制与依据 | “形成完整认知”等只宣布写作目的的句子 |
| 有效状态：已完成、计划、目标、未知和有条件的选择 | 以“闭环、推进、收口”替代具体对象和状态；或猜测历史代号 |
| 数据、指标定义、条件、来源与限制 | 编造数据，把目标当成结果，把进展记录当成效果验证 |
| 影响决策的差异、争议、未决问题和后续需要确认的信息 | 为使文字流畅而抹平矛盾，擅自替用户决定 |
| 有用的专业术语与必要解释 | 与本次汇报无关的术语全集、目录、起草和修订流水账 |
| 正文之外的原文问题清单：定位、依据、判断、处理状态及必要的待补信息 | 陌生术语一律判错、把业务未决当成表达错误、仅列未修复项或把建议当已修复 |

LexiFlow 原文还记录了此前协作的六项阅读要求：一个生命周期、按真实任务组织场景、目的先于实现清单、规则与操作分开维护、唯一正文与关联引用、有效链接与加粗格式。它们在文档整理样例中逐项核对；其中具体目录和治理分工只属于该项目，不写成所有场景必须遵循的通用规则。

删除或合并由句段的作用决定。`Harness`、`Registry`、`Formal`、`entry` 等不能直接当作黑话禁词；术语定义缺失时，依据目标读者判断是否构成解释缺口，缺领域知识则保留原意并交接。有效因果、条件、能力限制与授权边界也不能因含有过渡词或否定词被删除。

## 数据与评估约定

- [cases.json](cases.json) 是统一用例入口，包含构造场景、诊断与交接专项用例，以及三组真实文档用例。真实文档引用本目录相对路径，不把长原文塞进提示词。
- 每组 `input.md` 是执行者可见的材料；`reference.md`、`expectations.json`、`provenance.json` 是评估者资料，不得提前交给执行者。
- `must_include` 是应保留的信息，`must_exclude` 是不应出现的内容或错误推断；每项包含原文定位引句和判定理由。引句用于核对来源，不要求输出照抄。
- 验收项默认检查正文；`scope: issue_list` 单独检查问题清单。清单引用原文中的黑话或空话用于定位，不代表正文未清理。识别是否准确、修复是否可靠分别审阅，不能用改写流畅掩盖误报或漏报。
- 参考稿展示一种改法，不规定唯一结构、用词、长度。判定以信息和逻辑为准；参考稿与原文冲突时先修参考稿。
- `reference_status: proposed` 表示拟定稿；改为 `user_confirmed` 需要真实用户确认依据。模型执行或维护者自检均不能代替该确认。
- `tests/run.sh` 检查数据完整性、来源锚点、快照哈希和文件引用，不判断语义质量。实际执行、逐项判定与报告方法见 [rubric.md](rubric.md)，运行产物写入仓库 `tmp/skill-evals/feipi-writing-refine-text/`。
