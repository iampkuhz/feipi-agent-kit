# 时序图绘图规则

## 参与者声明

- 每个参与者必须使用 `participant`、`actor`、`database` 等 PlantUML 原生类型声明。
- 每个参与者必须用 `as <participants[].id>` 声明 alias。
- 不得新增 brief 中没有定义的核心参与者；如确需补辅助说明，只能用注释解释，不能加新图元。

## 分层（box / separator）

- 如 brief 中包含 `groups`，必须使用 `box "组名" #颜色 { ... } endbox` 包裹对应参与者。
- `box` 声明必须放在 `autonumber` 之后、消息之前。
- 如组的 `separator=true`，必须在该 `endbox` 后添加 `separator`。
- 参与者只能属于一个 `box`，不得重复声明。
- 颜色建议使用浅色系（如 `#DDDDDD`、`#EEEEEE`、`#FFFFFF`），避免干扰消息 readability。

## 消息

- 同步消息使用 `->`，返回消息使用 `-->`。
- 图中的每一条箭头消息都必须来自 brief；不得额外补一条“看起来合理”的返回或通知。
- 每条消息必须在箭头标签里落地 `Mx/Rx + 描述`。
- 标签过长时允许插入 `\\n` 换行，但不能删掉编号或改写关键命名。
- `activate` / `deactivate` 由绘图阶段按调用栈酌情添加，不作为 brief 必填字段。
- 数据存储类参与者（`type: database`）的消息一般不需要加 `activate` / `deactivate`。

## 分支逻辑（默认不支持）

- 当前模板和 schema 不建模 `alt` / `else` 分支。
- 若需求强依赖条件分支，先把主路径拆清，再决定是否扩展 brief，而不是直接在图里临时发挥。

## 布局

- 默认使用 `left_to_right direction`。
- 交付图必须同时设置 `skinparam nodesep` 与 `skinparam ranksep`。
- `layout.include_legend=true` 时必须包含 `legend`。
- 生命线过长时优先使用 `autonumber` 自动编号，不要手动维护序号。

## 交付前检查

1. 参与者 alias 是否与 brief 中的 `id` 一一对应。
2. 参与者名、消息编号、消息描述是否全部落图。
3. 图中是否出现 brief 未定义的额外消息或核心参与者。
4. 如 brief 包含 `groups`，是否正确使用 `box` / `separator` 分层。
5. 是否包含 `nodesep` / `ranksep`，且 `layout.include_legend=true` 时已落 `legend`。
6. 渲染图是否存在明显重叠、拥挤或标签遮挡。
