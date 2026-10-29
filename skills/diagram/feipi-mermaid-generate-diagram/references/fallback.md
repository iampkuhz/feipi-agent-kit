# 其他 Mermaid 图与现有源码

保留用户的业务图型名，例如 class、state、er、gantt，不改名为 fallback。brief 使用 `syntax` 指定 Mermaid 原生首行关键字，`expected_text` 列出必须出现的节点/动作/关键文本。完整例子为 `assets/examples/class.json` 与 `class.mmd`。

```bash
python3 scripts/run.py --brief class.json --diagram class.mmd --out-dir package
```

通用路径支持 schema 中列出的 Mermaid 原生语法，包含 classDiagram、stateDiagram-v2、erDiagram、gantt、pie、journey、gitGraph、timeline、requirementDiagram、quadrantChart、block-beta、architecture-beta 等。各语法是否可渲染以锁定 renderer 的真实结果为准；不为未试过的语法宣称专项语义覆盖。

保留用户源码但拒绝 init/frontmatter 配置、click 交互和脚本/外部图像嵌入。复杂样式若触发不支持的几何结构，报告失败并说明边界，不把自动检查缺失当通过。

与 typed profiles 不同，expected_text 仅证明文本存在。交付前必须按用户需求逐项检查全部节点、关系方向、基数、分支、日期/数值等，并查看 PNG/SVG。通过后 `review_package.py` 加 `--semantic-reviewed`，在 notes 中写明检查内容；没完成就保持 review_required。

C4 图的默认关系标签可能压在线上；查看图面后可用原生 `UpdateRelStyle(from,to,$offsetY="-15")` 定点移开文字，保留关系本身。参数见 [Mermaid C4 官方文档](https://mermaid.js.org/syntax/c4.html)。这类语法的连线几何不一定被通用选择器完整采集，因此视觉门禁不可省略。
