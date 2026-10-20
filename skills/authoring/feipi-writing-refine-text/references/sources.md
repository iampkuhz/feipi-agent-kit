# 参考来源与取舍

查阅日期：2026-10-16。以下公开 skill 用于设计比较；本 skill 的中文规则与示例独立编写，没有安装上游代码，也不要求运行时联网。链接指向可变化的上游文件，不作为固定版本声明。

| 来源 | 本 skill 采用的思路 | 本地取舍 |
|------|-------------------|----------|
| [Anthropic Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | 入口负责导航，详细规则按任务加载；资源直接从入口可达；用实际执行验证。 | 场景与条件资源分别路由；不把最大行数当设计目标，也不把分文件本身当作渐进加载已经生效。 |
| [Google Voice and tone](https://developers.google.com/style/tone) | 清晰有用优先，保留帮助理解的过渡，避免空泛措辞与机械句式。 | 按中文场景判断语气；不将英文写作风格或礼貌词规则一律套用到中文邮件。 |
| [blader/humanizer](https://github.com/blader/humanizer/blob/main/SKILL.md) | 从段落与句子的作用识别冗余；检查改写是否增删事实；清理对话残留；保护代码与链接。 | 按用户要求交付正文与原文问题清单；不把某个词或标点单独视为必须删除的证据。 |
| [ai-zixun/humanizer-zh](https://github.com/ai-zixun/humanizer-zh/blob/main/SKILL.md) | 区分中文文本用途，处理机械结构和空泛判断，保留原意及判断强度。 | 不主动提议模仿作者；不统一禁用破折号；不自动把技术缩写替换为近似中文概念。 |
| [nothing0here/humanizer-zh](https://github.com/nothing0here/humanizer-zh/blob/main/SKILL.md) | 关注职场黑话、无效连接及多场景语气。 | 仅参考问题分类；示例中的具体改写需要逐项核对原文，不能将“更具体”作为补造效果或事实的理由。 |

本地重点来自用户需求：以内容单位及其阅读作用判定重复，按逻辑关系判定过渡，转换内部历史与问答，并检查核心解释是否足够。诊断与修复分开，保留原文问题及处理状态供主 Agent 复核。五个优化方向、交接方式与具体中文示例是本仓库针对需求的设计，不能视为上游原有能力或质量结论。

这些来源提供编辑方法，不是文本作者身份的证据，也不构成 AI 检测准确率保证。本 skill 用信息保真和独立可读性评价改写结果。
