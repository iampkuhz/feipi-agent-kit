# 视觉风格路由

本文件不维护视觉数值。所有原子值以 `design-system/tokens/*.core.json` 为唯一真源。

## 风格原则

- 正式、克制、工程化；
- 标题先表达判断，主视觉承担主要认知任务；
- 证据和脚注不抢占中心；
- 网格、卡片、线条、圆角和留白使用登记 token；
- 同一语义角色在不同页面保持相同视觉层级；
- `Kaiti SC` 为首选主题字体，兼容别名只用于 fast/review 环境并记录 warning。

## 维护归属

- 字体、离散字号、字重和 role minimum：typography token；
- 颜色和语义色：color token；
- 页面、网格、间距和 padding：spacing token；
- 圆角和线宽：shape token；
- 组件 slot 和 size 的角色：Component Contract；
- region 几何和比例：Layout Contract。

`templates/style-locks/` 只引用 profile/token/layout，不是风格真源。文档、renderer、builder 和 validator 不得复制具体数值。

## 禁止

- AI 输出任意视觉值；
- 为容纳内容连续缩小字号；
- renderer 内 fallback 到未登记样式；
- 通过 LibreOffice 字体缺失改变最终主题字体；
- 让样例直接覆盖 token 或合同。
