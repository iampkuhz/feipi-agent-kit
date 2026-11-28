# Design System 使用边界

规范真源位于 `design-system/`：

- `tokens/`：唯一原子视觉值；
- `components/`：Component Contract；
- `layouts/`：Layout Contract；
- `profiles/`：引用组合；
- `composition-policy.md`：叙事与压缩。

`templates/style-locks/` 是派生产物，只引用 profile/token/layout。`helpers/pptx/theme.js` 是 TokenStore 派生的兼容只读视图。二者都不能独立维护数值。

样例 PPTX/截图只用于离线提取、人工确认和回归。运行时不读取全部样例；只加载当前候选 Layout 和实际使用的 Component Contract。

变更时先确定所有权：原子值改 token；slot/size/容量改 component；region/几何/替代策略改 layout；叙事改 composition。不要在 renderer 或文档补一个相同数值来“保持一致”。
