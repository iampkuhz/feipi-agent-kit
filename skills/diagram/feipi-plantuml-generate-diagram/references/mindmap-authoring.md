# Mindmap 编写指南

## 最短路径

1. 先把用户内容整理为一棵树：一个中心主题，通常 3–6 个一级分支，每个节点只写一个概念。同级采用一致的分类维度，不把处理顺序或交叉依赖强塞进树。
2. 只读取本指南与 `assets/templates/types/mindmap-brief.yaml`。从模板填写 `nodes: [{id, parent, label}]`，根的 `parent` 为 `""`；ID 只用于建模，不显示在图上。无需重复列边、深度和子节点。
3. `layout.direction` 默认填写 `right`，全部分支向右展开；仅在用户明确要求左右均衡或向左展开时分别用 `balanced` 或 `left`。balanced 根据子树叶节点文本行数估计高度，按 brief 同级顺序分配到较空的一侧；同一输入始终生成相同代码。
4. 先检查 brief，再执行批次 preflight；成功后运行生成器与统一图包验证。生成器是纯本地源码工具，不调用 renderer，也不声称完成了渲染验证。

以下命令在 skill 目录运行；`brief.yaml` 为已填写的输入，`out/` 为本图产物目录：

```bash
python3 scripts/lib/validate_brief_cli.py brief.yaml --type mindmap \
  --schema assets/validation/types/mindmap-brief.schema.json
bash scripts/preflight_renderer.sh --out renderer-preflight.json
# 仅在 preflight 成功后继续，复用回执里的 renderer_url。
python3 scripts/generate_mindmap.py --brief brief.yaml --out out/diagram.puml
bash scripts/validate_package.sh --diagram-type mindmap --brief brief.yaml \
  --diagram out/diagram.puml --out-dir out --server-url http://127.0.0.1:8199
```

最后命令的 URL 须替换为回执中的实际地址。单图首次渲染一次，修复最多一次；其余失败与缓存规则沿用主入口。不要额外调用内部 verifier。

## 受支持的源码写法

- 定界符必须是独立的 `@startmindmap` / `@endmindmap`，只允许一个单根图。
- 默认生成 arithmetic：`+ 根`、`++ 右分支`、`+++ 右分支的子节点`；左分支用 `--`、`---`。符号个数就是含根的层级；不能跳级或把子节点接到另一侧。
- 手写也支持 OrgMode：`* 根`、`** 分支`、`*** 子节点`，独立 `left side` / `right side` 在一级分支边界切换；一次图内不要混用两套表示法。OrgMode 必须靠星号个数表达层级，不能靠缩进表达层级。
- 标签换行在 YAML 中使用真实换行（例如双引号字符串里的 `\n`），生成器写成 PUML 的字面 `\n`。建议优先精简短语，让 `MaximumWidth` 自动折行。每个标签最多 3 个显式行、96 显示列（汉字通常占两列）。
- 支持 `++[#DBEAFE] 标签` 的节点填色、`+++_ 叶节点` 的去边框，以及节点末尾 `<<style_name>>` 的样式名。推荐直接复用生成器的样式。
- 标签使用纯文本；不支持 HTML/Creole、超链接、图标、外部 include、宏、多根、Markdown 标题/缩进列表、冒号分号多行块或跨分支连线。这是本 profile 的可验证子集，不表示 PlantUML 本身不支持这些语法。遇到超范围输入须说明缺口，不静默降级或伪报通过。

最小层级示意（交付时还需加入默认 style）：

```plantuml
@startmindmap
+ 核心主题
++ 目标
+++ 预期成果
-- 行动
--- 下一步
@endmindmap
```

## 默认外观与内容预算

- 白色背景、深色文字、浅色分支填充；同一一级分支及其后代共享颜色。根节点加大加粗，正文 14，圆角 12，细灰线，关闭阴影。
- 样式真源为 `assets/templates/types/mindmap-style.puml`，生成时内联，输出不依赖远程主题或 include。
- 节点自动折行宽度 180 px、内边距 10、外边距 8。mindmap 使用原生 `node/rootNode/arrow` 样式，不能套用架构图的 `nodesep/ranksep` 或强制 legend。
- 推荐 12–24 个节点、2–4 层；硬预算为 2–32 个节点、含根最多 4 层、每节点最多 6 个直接子节点。超限先归并概念或拆为总览与分支子图，不通过缩小字体挤入一张图。
- 同父节点下的标签应唯一；不同分支可复用相同文本。覆盖检查对比完整父子路径、文本、左右归属和出现次数，不通过全文件搜索文字冒充覆盖。

## 验证与视觉复核

自动检查：schema、唯一根、ID/父引用、循环、同级重复、预算、源码层级、左右归属、布局参数、真实 SVG、源码 metrics 与图包 hash。`validation.json` 成功表示这些门禁通过。

交付前查看 SVG：确认中文可读无缺字、标题不过长、方向符合 brief（balanced 时左右视觉重量相近）、无挤压或截断、同级文字粒度一致。自动预算与样式检查不等于审美判断，未查看图像时必须说明视觉未复核。若中文缺字，报告 renderer 字体环境限制，不擅自修改服务。

## 语法依据

核对日期：2026-09-09。官方 [MindMap 文档](https://plantuml.com/mindmap-diagram) 用于核实 arithmetic、OrgMode、左右分支、颜色和样式语法；本仓库默认样式与预算属于维护约定。示例必须经过当前本地 renderer 的真实渲染验证。
