# 意图路由表

## 路由规则

| 用户表达 | mode | summary_style | news | external_context |
|----------|------|---------------|------|------------------|
| "总结视频" / "这个视频讲了什么" / "帮我总结一下" | summary | structured | off | off |
| "只总结，不扩展" / "只根据视频内容总结" / "不要评价不要背景" | summary | strict | off | off |
| "总结并评价" / "这个视频怎么看" / "有什么启发" / "分析一下这个视频" | summary | review | off | off |
| "操作步骤" / "怎么做" / "checklist" / "可执行清单" / "这个视频怎么做" | summary | tutorial/action | off | off |
| "补充背景" / "来龙去脉" | expand 或 background-only | background | off | on |
| "最新进展" / "相关新闻" / "现状" | expand 或 background-only | background | on | on |

## summary_style 定义

| 值 | 说明 | 允许 | 禁止 |
|----|------|------|------|
| `strict` | 只基于视频转写文本做结构化整理 | 结构化整理、时间锚点、来源状态 | 外部背景、模型评价、相关新闻 |
| `structured` | 默认结构化总结 | 提炼结构/主线/观点/案例/结论 | 主动扩展背景、主动搜索新闻 |
| `review` | 允许模型分析和评价 | 启发/局限/可借鉴之处/需要额外核验 | 把模型评价伪装成视频原话 |
| `tutorial` | 教程类，优先步骤和配置 | 步骤/命令/配置/注意事项/验证方式 | 强行写"核心观点/论证结构/局限性" |
| `action` | 可执行清单 | checklist/命令/参数/二次确认标记 | 不确定的参数伪装为确定 |
| `background` | 背景模式专用 | 外部资料、历史背景、术语解释 | 把视频内复述冒充背景 |

## video_type 识别规则

video_type 由模型在 prompt 中根据标题和 transcript 自行判断：
- 不要求输出冗长分类理由
- 无法判断时使用 `other`
- 视频类型定义见 `video_type_templates.md`
