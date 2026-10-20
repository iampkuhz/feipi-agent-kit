## 1.5. 文档整理与验证边界

目录与合同整理已落地：唯一工程入口是 [docs/README](../../../README.md)，系统主题、真实任务和查阅分别位于 system、scenarios、reference；roadmap 与 user 保留独立职责。原三个视角目录已合并删除，Harness、Catalog、风险路径及引用者同步，未降低门禁覆盖。

本轮文档按深度精简实现同步：开发只保留唯一 diff 报告与精确诊断，Registry 合并 canonical Check/scene 和 CI policy，Git 提醒入口删除，环境与来源身份保持真实认证，Codex 每 Task 只引用不可变父合同，Gate 使用唯一活动 namespace 和最新 schema。六个受影响图已从 ignored 草稿实际校验、渲染、查看并原样复制；文档静态检查通过只证明链接和结构，不构成独立验收。用户已确认无外部旧运行或收据需要续用，Qoder 委派与旧事实消费说明已退役；仅保留手工客户端 Stop 与权限 profile。源码集成与独立验收按后续真实证据报告。

| 用户要求 | 当前实现 | 核对入口 |
| --- | --- | --- |
| 一个生命周期，阶段清晰 | 通用范围与验收合并；实现自检和交付证明分层；维护包括文档，无额外反馈阶段 | [总入口](../../../README.md) |
| 场景不是组件 | 修改导入、执行门禁、优化门禁分别成页；优化页回链执行页，不复制运行子图 | [功能变更](../../../scenarios/change-lexicon-import.md)、[执行](../../../scenarios/run-repository-gates.md)、[优化](../../../scenarios/optimize-repository-gates.md) |
| 阅读分层；目的先于实现清单 | 总览区分三体系；操作入口按目标选择；逐项检查库存侧链到 Reference，不把用途、场景、范围、入口混为层次 | [工程总览](../../../system/engineering.md)、[执行场景](../../../scenarios/run-repository-gates.md)、[检查清单](../../../reference/verification/check-catalog.md) |
| 原则属于 Harness | 文档人类规则在 Harness Markdown，docs 只保留导航与维护操作，不另存原则清单 | [documentation-policy](../../../../harness/documentation-policy.md)、[维护步骤](../../../scenarios/maintain-documentation.md) |
| 唯一正文及关联引用 | 来源／字幕合并；决策理由随系统主题维护；总入口和本机操作索引合并；未改图保留字节，修订的共用检查图重新校验、渲染与视觉核对后复制正文 | [系统](../../../system.md)、[本机开发](../../../scenarios/local-development.md) |
| IDE 链接和加粗 | 主导航采用相对文件链接；结束加粗标记与后文分隔 | 相对链接与片段已静态核对；本轮未重新执行 IDE 实点，阅读效果由用户 review 确认 |

文档内容与文件地图已做独立只读复核。最新完成的静态检查覆盖 58 个文件、25 张内嵌图；现有正文图源有校验与预览证据。配置精简同步两张相关图，按 skill 重新渲染与视觉核对后复制正文，最终检查以统一冻结后的报告为准，不借文档自检声称 Formal 或真实发行通过。
