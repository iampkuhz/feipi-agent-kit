# 架构组件图需求模板

## 用途

本模板用于定义**架构组件图**的 diagram-brief 格式。

**适用场景**：
- 区块链技术协议架构
- 系统组件分层关系
- 跨层流程可视化

---

## 模板结构

```yaml
# =====================
# 必填字段
# =====================

# diagram_id: 用于标识本图，建议格式 <topic>-<diagram-type>
diagram_id: eip-4337-architecture

# diagram_type: 架构组件图固定为 "architecture"
diagram_type: architecture

# title: 图标题
title: "EIP-4337 架构组件图"

# =====================
# 分层定义（必填，至少 3 层）
# =====================

layers:
  - id: protocol
    name: 协议层
    description: 协议核心组件
    color: "#E3F2FD"  # 浅蓝
  - id: data
    name: 数据层
    description: 数据对象
    color: "#FFF9C4"  # 黄色
  - id: external
    name: 外部参与方
    description: 用户、验证者等
    color: "#E0E0E0"  # 灰色

# =====================
# 组件清单（必填，至少 3 个）
# =====================

components:
  # 组件类型：component | actor | database | note | interface | queue
  - id: entrypoint
    name: EntryPoint
    layer: protocol      # 必须引用 layers 中定义的 id
    description: 智能账户入口合约
    type: component      # component/actor/database/note/interface/queue

  - id: bundler
    name: Bundler
    layer: protocol
    description: 操作打包器
    type: component

  - id: proposer
    name: 提议者
    layer: external
    description: 发起交易的用户
    type: actor          # actor 显示为人形

  - id: userop
    name: UserOperation
    layer: data
    description: 用户操作对象
    type: note           # note 显示为黄色矩形

# =====================
# 跨层流程（必填，至少 1 个）
# =====================

flows:
  - id: S1
    from: proposer       # 必须引用 components 中定义的 id
    to: entrypoint
    description: 提交 UserOperation

  - id: S2
    from: entrypoint
    to: bundler
    description: 打包操作

# =====================
# 可选字段
# =====================

# 边界条件：说明哪些内容不在图内
boundaries:
  - 不包含：底层共识机制细节
  - 不包含：具体代码实现

# 特殊要求
requirements:
  - 使用纵向布局 (top to bottom direction)
  - 箭头必须标注 S 序号
  - 必须包含图例
```

---

## 字段说明

### 必填字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `diagram_id` | string | 图的标识符，用于文件命名 | `eip-4337-architecture` |
| `diagram_type` | string | 图类型，架构组件图固定为 `architecture` | `architecture` |
| `title` | string | 图标题 | "EIP-4337 架构组件图" |
| `layers` | array | 分层定义，至少 3 层 | 见下表 |
| `components` | array | 组件清单，至少 3 个 | 见下表 |
| `flows` | array | 跨层流程，至少 1 个 | 见下表 |

### layers[] 字段

| 字段 | 类型 | 说明 | 必填 |
|------|------|------|------|
| `id` | string | 分层标识符，用于 components.layer 引用 | 是 |
| `name` | string | 分层名称，显示在图中 | 是 |
| `description` | string | 分层描述 | 是 |
| `color` | string | 背景色（十六进制） | 是 |

### components[] 字段

| 字段 | 类型 | 说明 | 必填 |
|------|------|------|------|
| `id` | string | 组件标识符，用于 flows.from/to 引用 | 是 |
| `name` | string | 组件名称，显示在图中 | 是 |
| `layer` | string | 所属分层，必须引用 layers[].id | 是 |
| `description` | string | 组件描述 | 是 |
| `type` | string | 组件类型：`component`/`actor`/`database`/`note`/`interface`/`queue` | 是 |

### flows[] 字段

| 字段 | 类型 | 说明 | 必填 |
|------|------|------|------|
| `id` | string | 流程标识符（如 S1, S2），显示在箭头上 | 是 |
| `from` | string | 起始组件，必须引用 components[].id | 是 |
| `to` | string | 目标组件，必须引用 components[].id | 是 |
| `description` | string | 流程描述 | 是 |

---

## 校验规则

本模板自动触发以下校验：

### 1. 完整性校验

```python
# 必填字段检查
required_fields = ['diagram_id', 'diagram_type', 'title', 'layers', 'components', 'flows']

# 数量约束
min_layers = 3
min_components = 3
min_flows = 1
```

### 2. 引用有效性校验

```python
# 提取所有组件 ID
comp_ids = [c['id'] for c in components]

# 检查每个 flow 的 from/to 是否都在 comp_ids 中
for flow in flows:
    assert flow['from'] in comp_ids, f"flow '{flow['id']}' 的 from 引用了未定义的组件"
    assert flow['to'] in comp_ids, f"flow '{flow['id']}' 的 to 引用了未定义的组件"
```

### 3. 需求覆盖校验

生成 PlantUML 后，校验：
- 所有 components[].name 都出现在 PlantUML 代码中
- 所有 flows[].id 都作为箭头标注出现在 PlantUML 代码中

---

## 使用示例

### 示例 1：填写 brief 并调用 skill

**步骤 1**：复制模板，保存为 `diagrams/briefs/active/my-arch-brief.yaml`

**步骤 2**：填写必填字段

**步骤 3**：调用 skill
```
请使用 feipi-gen-plantuml-code：
- 输入：diagrams/briefs/active/my-arch-brief.yaml
```

### 示例 2：直接粘贴 brief 内容

```
请使用 feipi-gen-plantuml-code，帮我画一个架构图：

```yaml
diagram_id: consensus-arch
diagram_type: architecture
title: "Malachite 共识架构图"
layers:
  - id: protocol
    name: 协议层
    description: 共识核心组件
    color: "#E3F2FD"
  - id: data
    name: 数据层
    description: 数据对象
    color: "#FFF9C4"
  - id: external
    name: 外部参与方
    description: 验证者节点
    color: "#E0E0E0"
components:
  - id: proposer
    name: Proposer
    layer: protocol
    description: 提议者节点
    type: component
  - id: validator
    name: Validator
    layer: protocol
    description: 验证者节点
    type: component
  - id: vote
    name: Vote
    layer: data
    description: 投票消息
    type: note
flows:
  - id: S1
    from: proposer
    to: validator
    description: 广播提议
```
```

---

## 配色建议

| 分层类型 | 推荐颜色 | 十六进制 |
|----------|----------|----------|
| 协议层（蓝色系） | 浅蓝背景，深蓝边框 | `#E3F2FD` / `#1565C0` |
| 数据层（黄色系） | 浅黄背景，深黄边框 | `#FFF9C4` / `#F9A825` |
| 外部参与方（灰色系） | 浅灰背景，深灰边框 | `#E0E0E0` / `#424242` |
| 存储（绿色系） | 浅绿背景，深绿边框 | `#C8E6C9` / `#2E7D32` |

---

## 相关文件

- `assets/architecture-diagram-styles.puml`：PlantUML 样式库（可直接引用）
- `references/component.md`：component 图详细规范
- `SKILL.md`：skill 入口说明
