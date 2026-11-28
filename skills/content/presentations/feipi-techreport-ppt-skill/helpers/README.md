# Helpers

`helpers/` 只保留后端原语、静态 QA、兼容入口和运行时辅助。设计真源与编译职责不在此目录。

```text
compiler/                   # token、contract、IR、Render Plan、overflow
adapters/                   # PPTX 后端接口与实现
helpers/
├── static-qa.js            # 编译后静态 QA
├── semantic-rules.js       # role-aware 字号、重叠、截断和越界规则
├── pipeline/run-pipeline.js# 单次状态机编排
├── pptx/
│   ├── theme.js            # TokenStore 派生的兼容只读视图
│   ├── primitives.js       # 仅消费已解析 Render Plan
│   ├── compiler.js         # 旧 CLI 的薄兼容入口
│   └── postcheck.js        # OpenXML/可编辑性检查
└── design-kit/             # 旧 design-kit fixture 的仓内 adapter
```

约束：

- helper 不定义字体、字号、颜色、padding、圆角或布局坐标；
- renderer 缺少 resolved token 时硬失败；
- 不允许 autofit、连续缩放或未知字号 fallback；
- `helpers/design-kit/` 不读取用户 Downloads；
- 通用 PPTX 能力通过 adapter 隔离，不能扩张为第二套设计系统。
