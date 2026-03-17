---
name: feipi-gen-plantuml-code
description: 用于根据输入需求生成并校验 PlantUML 代码，覆盖图类型判断、布局约束、渲染验证与可读性复核。在用户要画流程图、模块图、时序图或类图并要求结果可直接渲染时使用。
---

# PlantUML 代码生成与校验（中文）

## 核心目标

输入自然语言需求，先生成 PlantUML 代码，再自动校验语法与渲染可用性。

## 触发场景

1. 需要把系统流程、组件关系、时序关系转换为 PlantUML。
2. 需要在交付前自动验证语法，避免“写完不可渲染”。
3. 需要控制图宽度，避免横向过宽导致阅读困难。

## 非适用场景

1. 只要 Mermaid、Draw.io 或非 PlantUML 图，不需要 PlantUML 代码。
2. 只要一句口头结构建议，不需要真实可渲染图代码。
3. 用户要求当前 skill 未支持的图类型，且不接受改写为 component/sequence/class。

## 先确认什么

1. 必填
- 图类型：`component`、`sequence` 或 `class`
- 图需求描述：核心元素、关系、流程或约束

2. 按需确认
- 是否要控制宽度、配色或分层
- 是否有标题、关键编号或必须保留的术语

默认策略：
1. 组件与模块关系优先用 `component`。
2. 有时间顺序、交互往返优先用 `sequence`。
3. 有实体、属性、关联优先用 `class`。
4. 图类型不明确时，先根据用户意图选一个默认类型，不在一开始给过多并列方案。

## 强约束

1. 生成后必须自动校验
- 每次产出 `.puml` 后，必须执行：
```bash
bash scripts/check_plantuml.sh <input.puml>
```
- 仅当 `syntax_result=ok` 才可交付最终代码。

2. 渲染器优先级
- 统一从 `assets/server_candidates.txt` 读取单一候选列表，按顺序逐个尝试，不区分“本地/远程”分支。
- 本地 server 端口默认 `8199`，可通过环境变量 `AGENT_PLANTUML_PORT` 覆盖。
- 若语法错误，直接返回错误，不继续切换其他 server 掩盖问题。

3. 宽度控制
- component/class 等非 sequence 图：元素较多时必须使用 `top to bottom direction`。
- sequence 图不要使用 `top to bottom direction`（该语法会报错），改为减少参与者数量、拆分子图。
- 推荐同时设置：`skinparam nodesep` 与 `skinparam ranksep`。
- 长标签必须换行（newline），避免单行文字拉宽画布。
- 校验命令会自动执行布局检查：
```bash
bash scripts/lint_layout.sh <input.puml>
```

4. component 图专属要求
- 模块必须分层（至少 3 层）。
- 不同层颜色必须可区分。
- 跨层流程必须用 edge 串联，流程序号从 `S1` 开始。
- 详见：`references/component.md`。

5. 渲染后必须做可读性复核
- 每次生成 `*.svg` 后，必须查看渲染图像本身（image），不能只看 `*.puml` 源码。
- 若出现 edge 文本重叠、标签遮挡、线条交叉导致难读，视为未完成，不可交付。
- 必须继续优化直到可读性达标，允许且推荐：
  - 简化 edge 文案（如仅保留 `S1..Sn`，详细说明移到 `legend`/`note`）
  - 调整布局与路由（`right/down/up`、`-[hidden]->`、`nodesep/ranksep`）
  - 必要时拆分为子图，避免单图信息过载

6. 图类型 reference 拆分
- 不同图类型必须有各自独立 reference 文件。
- 当前索引见：`references/reference-index.md`。
- 新图类型按模板新增：`references/diagram-reference-template.md`。

## 输入与输出

1. 输入
- 必选：图需求描述（目标、元素、关系、约束）
- 可选：图类型（component/sequence/class）、标题、配色偏好

2. 输出
- `*.puml`：PlantUML 源码
- `*.svg`：渲染结果（由校验脚本自动输出）
- 校验日志：`server_url`、`server_mode`、`syntax_result`

## 工作流（使用态）

1. Explore
- 明确图类型、核心元素、关系方向、约束条件。
- 按图类型加载对应 reference：
  - component：`references/component.md`
  - sequence：`references/sequence.md`
  - class：`references/class.md`

2. Plan
- 先规划布局策略（分区、上下层级、换行点）。
- component 图需要先定义“层级 + 颜色 + S 序号流程”。

3. Implement
- 使用生成脚本产出 `.puml`：
```bash
bash scripts/generate_plantuml.sh --type component --requirement "<需求>" --output ./tmp/diagram.puml
```

4. Verify
- 执行语法 + 渲染校验：
```bash
bash scripts/check_plantuml.sh ./tmp/diagram.puml --svg-output ./tmp/diagram.svg
```
- 若报语法错误，修复后重跑，直到 `syntax_result=ok`。
- 语法通过后必须做图像复核：检查是否存在文字重叠/遮挡；若有则继续迭代优化再重跑校验。

## 常见失败与修复

1. 图能渲染，但横向过宽
- 处理：优先改成纵向布局、缩短长标签、增加换行点。

2. sequence 图报 `top to bottom direction` 相关错误
- 处理：移除该语法，减少参与者数量或拆分子图。

3. component 图流程编号混乱
- 处理：统一改成 `S1...Sn`，并确保正文或图例解释同步。

4. 语法通过但图难读
- 处理：先简化 edge 文案，再调整布局、隐藏线或拆图，不把“能渲染”当成交付完成。

## 标准命令

1. 根据需求生成 puml
```bash
bash scripts/generate_plantuml.sh --type component --requirement "模块分层、分色、S1 流程" --output ./tmp/diagram.puml
```

2. 直接校验（按候选列表顺序尝试）
```bash
bash scripts/check_plantuml.sh ./tmp/diagram.puml
```

3. 单独执行布局校验
```bash
bash scripts/lint_layout.sh ./tmp/diagram.puml
```

4. 渲染后转图片并人工复核（推荐）
```bash
rsvg-convert ./tmp/diagram.svg -o ./tmp/diagram.png
```

## 验收标准

1. `scripts/generate_plantuml.sh` 能根据需求生成 `*.puml`。
2. `scripts/check_plantuml.sh` 可输出 `syntax_result=ok|error`。
3. 候选列表中的前序 server 不可用时，会自动尝试后续 server。
4. component 图满足“分层、分色、S1 起始流程 edge”约束。
5. 渲染图通过人工可读性复核：edge 文本无明显重叠/遮挡，关键流程可辨识。
6. “需求文本 -> 生成代码 -> 真实渲染校验”链路可执行，不依赖预置正确 puml。

## 渐进式披露导航

- 图类型索引：`references/reference-index.md`
- component 样例：`references/component.md`
- sequence 参考位：`references/sequence.md`
- class 参考位：`references/class.md`
- 新图类型模板：`references/diagram-reference-template.md`
- 来源说明：`references/sources.md`
