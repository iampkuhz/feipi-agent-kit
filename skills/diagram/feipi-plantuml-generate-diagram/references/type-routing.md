# 类型识别与路由规则

## Router 职责

Router 只负责判断用户意图属于哪种 PlantUML 图，不做复杂校验。

## 识别规则

### 显式类型（优先级最高）

用户在自然语言中明确提到图类型关键词：

| 关键词示例 | 路由到 profile |
|-----------|---------------|
| 架构图、系统架构、模块分层 | `architecture` |
| 时序图、交互图、调用链路、消息流转 | `sequence` |
| 活动图、流程图、activity diagram | `activity` |
| 组件图、组件关系图、component diagram | `component` |
| 部署图、物理边界、deployment diagram | `deployment` |

`class`、`state`、`usecase` 等未注册类型保留请求类型，但进入 `fallback`；不得因为文档提到该类型就当作 typed profile。

### 可推断类型

用户未明确说图类型，但描述中包含可推断关键词：

- "参与者"、"调用"、"返回"、"时序"、"消息" → 推断 `sequence`
- "层"、"组件"、"依赖"、"架构"、"分层" → 推断 `architecture`
- "步骤"、"分支"、"活动"、"流程" → 推断 `activity`
- "物理区"、"跨网"、"离线"、"HSM"、"人工交接" → 推断 `deployment`

### 不确定类型

关键词不明确或完全不匹配任何 profile → 进入 `fallback`。

## 路由优先级

1. brief YAML 中 `diagram_type` 字段 > 显式关键词 > 可推断关键词 > fallback
2. Router 不应拒绝用户，识别不了也要进入 fallback 生成图。

## Fallback 触发条件

- 用户请求中无图类型关键词
- 描述同时匹配多个类型且无法消歧
- brief 未提供 `diagram_type`、类型未注册或值不合法
