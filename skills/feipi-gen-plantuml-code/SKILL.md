---
name: feipi-gen-plantuml-code
description: 用于根据 diagram-brief 需求模板或自然语言描述生成并校验 PlantUML 代码。在用户需要画架构图、时序图或类图，且要求结果可直接渲染时使用。支持两种输入方式：优先使用 diagram-brief 模板（正式交付），备选使用自然语言（快速原型）。
---

# PlantUML 代码生成与校验

## 核心目标

根据用户提供的 diagram-brief 模板或自然语言需求，生成可渲染的 PlantUML 代码，并自动校验语法、布局和需求覆盖度。

**两段式架构**：
1. **发起方**（用户）：填写 brief 需求模板，对需求完整性负责
2. **画图方**（本 skill）：读取 brief → 校验完整性 → 生成 PlantUML → 校验图与需求一致性

**关键原则**：
- 如用户未提供完整的 brief，必须先反问获取缺失信息，不得自行猜测
- 不得添加 brief 中未定义的组件或流程
- 生成的图必须通过需求覆盖校验（brief 中所有组件和流程都体现在图中）

---

## 触发场景

### 方式 A：用户已填写 diagram-brief（优先）

**典型触发**：
- "请根据这个 brief 生成架构图：`diagrams/briefs/active/xxx-brief.yaml`"
- "帮我画个图，brief 内容如下：（粘贴 yaml）"
- "我们已经有需求模板了，请生成 PlantUML"

**输入要求**：
- brief 文件路径，或 brief 内容
- 或指定图类型（architecture/sequence/class）

### 方式 B：用户仅提供自然语言描述（备选）

**典型触发**：
- "画一个 EIP-4337 的架构图"
- "帮我画个时序图，展示 A 调用 B 再调用 C 的流程"

**输入要求**：
- 图需求描述（核心元素、关系、流程）
- 图类型（如用户未指定，需主动询问）

---

## 非适用场景

1. 只需要 Mermaid、Draw.io 等非 PlantUML 图
2. 只需要口头结构建议，不需要可渲染代码
3. 用户要求的图类型当前 skill 不支持（当前支持：architecture/component、sequence、class）

---

## 先确认什么（关键）

### 第一步：判断输入方式

**如用户已提供 brief 文件或内容**：
→ 进入「diagram-brief 流程」

**如用户仅提供自然语言**：
→ 进入「自然语言流程」

### 第二步：diagram-brief 流程 — 检查文件完整性

**必须检查以下必填字段**：

| 字段 | 说明 | 缺失时反问 |
|------|------|-----------|
| `diagram_id` | 图的标识符 | "请给这个图一个标识符（如 `eip-4337-arch`），用于文件命名和引用" |
| `diagram_type` | 图类型 | "请指定图类型：`architecture`（架构图）/ `sequence`（时序图）/ `class`（类图）" |
| `title` | 图标题 | "请给这个图一个标题" |
| `layers` | 分层定义（至少 3 层） | "请定义至少 3 个分层（如协议层、数据层、外部参与方），每层需包含：id、name、description、color" |
| `components` | 组件清单（至少 3 个） | "请列出至少 3 个组件，每个组件需包含：id、name、layer、type（component/actor/database/note）" |
| `flows` | 跨层流程（至少 1 个） | "请定义至少 1 个流程，每个流程需包含：id、from、to、description" |

**如任何必填字段缺失**：
→ **必须暂停执行**，反问用户获取缺失信息
→ 可提供模板示例帮助用户填写

**如所有必填字段完整**：
→ 进入生成阶段

### 第三步：自然语言流程 — 确认需求

**必须确认**：
- 图类型（component/sequence/class）
- 核心组件/元素列表
- 主要流程或关系

**如信息不足**：
→ 反问用户补充

---

## 执行流程

### diagram-brief 流程

1. **读取 brief**
   - 如用户提供文件路径 → 读取文件
   - 如用户粘贴内容 → 解析 YAML

2. **完整性校验**
   - 检查必填字段
   - 检查数量约束（layers≥3, components≥3, flows≥1）
   - 检查引用有效性（flow.from 和 flow.to 必须在 components 中定义）

3. **如校验失败**
   - 返回缺失清单
   - 提供模板示例
   - **暂停执行，等待用户补充**

4. **如校验通过**
   - 根据 diagram_type 加载对应 reference
   - 根据 brief 生成 PlantUML 代码
   - 执行语法校验
   - 执行需求覆盖校验
   - 输出 .puml 和 .svg

### 自然语言流程

1. **明确需求**
   - 如信息不足，反问用户
   - 根据用户回答整理需求

2. **生成 PlantUML**
   - 根据需求生成代码
   - 执行语法校验

3. **输出结果**
   - 交付 .puml 源码
   - 如可能，提供 .svg 渲染

---

## 强约束

### 1. 生成后必须自动校验

每次产出 `.puml` 后，必须执行：
```bash
bash scripts/check_plantuml.sh <input.puml>
```
仅当 `syntax_result=ok` 才可交付最终代码。

### 2. 渲染器优先级

- 统一从 `assets/server_candidates.txt` 读取候选列表
- 优先尝试本地 server（端口 8199）
- 若语法错误，直接返回错误，不切换 server 掩盖问题

### 3. 宽度控制

- component/class 图等元素较多时必须使用 `top to bottom direction`
- sequence 图不要使用 `top to bottom direction`
- 长标签必须换行

### 4. component 图专属要求

- 模块必须分层（至少 3 层）
- 不同层颜色必须可区分
- 跨层流程必须用 edge 串联，流程序号从 `S1` 开始
- 详见：`references/component.md`

### 5. 渲染后必须做可读性复核

- 必须查看渲染图像，不能只看源码
- 如出现重叠、遮挡，必须继续优化
- 允许简化 edge 文案、调整布局、拆分子图

---

## 输入与输出

### 输入

**diagram-brief 方式**：
- brief 文件路径或 YAML 内容

**自然语言方式**：
- 图需求描述
- 图类型（如未指定需询问）

### 输出

- `.puml`：PlantUML 源码
- `.svg`：渲染结果（如环境支持）
- 校验报告（包含完整性校验、需求覆盖校验、语法校验结果）

---

## 规则索引

- `references/component.md`：component 图详细规范
- `references/sequence.md`：sequence 图详细规范
- `references/class.md`：class 图详细规范
- `references/template-architecture-brief.md`：架构组件图 brief 模板说明

---

## 资产索引

- `assets/templates/architecture-brief.yaml`：架构组件图 brief 模板
- `assets/architecture-diagram-styles.puml`：架构图样式库

---

## 常用命令

```bash
# 生成 PlantUML
bash scripts/generate_plantuml.sh --type component --requirement "<需求>" --output ./tmp/diagram.puml

# 校验语法
bash scripts/check_plantuml.sh ./tmp/diagram.puml --svg-output ./tmp/diagram.svg

# 布局校验
bash scripts/lint_layout.sh ./tmp/diagram.puml

# 渲染转图片
rsvg-convert ./tmp/diagram.svg -o ./tmp/diagram.png
```
