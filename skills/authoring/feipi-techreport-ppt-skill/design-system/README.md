# Design System

本目录是中文技术汇报 PPT 视觉与组件合同的唯一上游真源。样例只用于离线提取和回归，不直接决定运行时样式。

```text
design-system/
├── tokens/                  # 原子视觉值唯一真源
├── components/              # Component Contract
├── layouts/                 # Layout Contract
├── profiles/                # 只组合引用，不复制数值
├── composition-policy.md    # 语义、叙事与信息压缩
├── patterns/                # 组合模式说明
└── samples/                 # 开发期参考，不进默认上下文
```

## 单一事实源

| 规则 | 维护位置 |
|---|---|
| 字体、离散字号、角色最小字号、颜色、间距、圆角、线宽、页面、网格 | `tokens/*.core.json` |
| slots、variants、sizes、text role、容量、嵌套、overflow、编辑性和 QA | `components/*.json` |
| 认知任务、固定 regions、允许组件、容量、替代布局和禁止模式 | `layouts/*.layout.json` |
| 结论提炼、主视觉选择、压缩和拆页 | `composition-policy.md` |

`templates/style-locks/` 是派生 profile，只能引用 token 和 layout，不得复制视觉数值。Renderer、builder、validator 和文档不得维护第二套字号或颜色。

## 编译约束

- `compiler/token-store.js` 是唯一 token 读取路径；未知、缺失或循环引用硬失败。
- Component/Layout Contract 由 `compiler/contract-registry.js` 读取并校验 token 引用。
- Semantic Slide IR 只能选择登记的 id、variant、size、region 和 text role。
- 只有 Render Plan 可以包含解析后的 pt 与 EMU；Renderer 只消费 Render Plan。
- 禁止数字字号 fallback、连续缩放、自动字号和任意坐标。

## 当前 P0 合同范围

P0 已建立三个固定 Layout Contract：分层架构、方案对比、多方交互流程。其余组件和页面类型在 P1 逐步升级为完整 v2 合同；未升级条目不能作为新 v2 页面中的自由样式入口。

## 维护流程

1. 判断需求应落在 token、Component Contract、Layout Contract 还是 Composition Policy。
2. 只修改对应真源，不在 consumer 中复制值。
3. 更新 schema/编译器测试和代表 fixture。
4. 运行：

```bash
node scripts/validate_design_system.js
bash scripts/test.sh
```

人工认可的 PPTX 或截图应先离线提取并确认，再写回真源；不得要求运行时模型重新理解全部历史样例。
