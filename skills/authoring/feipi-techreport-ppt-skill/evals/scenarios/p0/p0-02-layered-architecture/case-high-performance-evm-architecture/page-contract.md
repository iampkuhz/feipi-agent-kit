# Page Contract: P0-02 分层架构 / 组件结构图页

## Layout

- 16:9 单页。
- 左侧主架构图占页面 58%–68%。
- 右侧分类说明占页面 28%–36%。
- 页面标题在左上方，不能挤压主图。

## Required Regions

1. Title region
2. Validator overview region
3. Expanded validator layered architecture region
4. Offchain nodes region
5. Improvement taxonomy region

## Architecture Requirements

- 必须体现层级：共识层、执行层、OS/硬件/ECS。
- 必须有至少 1 个展开的 Validator。
- 必须有 RPC 节点、索引节点、监控/日志。
- 改造点标签必须和右侧说明一一对应。
- 箭头只表达关键依赖，不允许箭头过密。

## Style

- 共识层、执行层、基础设施层使用不同浅色底。
- 改造点标签使用短标签。
- 右侧分类说明采用 A/B/C/D 分组卡片。
