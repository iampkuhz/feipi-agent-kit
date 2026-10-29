# 图型 brief 与质量预算

所有图包含 `diagram_id`、`diagram_type`、`title`、`summary`、`layout`。JSON/YAML 均可；拒绝重复键、YAML alias、未知字段、控制字符。完整可执行字段约束见 `assets/brief.schema.json`。示例均可直接运行，修改时保留用户实际语义。

| 图型 | 输入结构 | 预算与语义门禁 |
|---|---|---|
| architecture | groups、nodes、edges | 3–6 层，3–12 节点，每层≤5，1–16 边，TB 纵向；分层、节点、关系双向完整 |
| sequence | participants、messages，可选 groups、blocks、numbering | 2–8 参与者、1–20 消息、≤5 块；引用、顺序、编号、note、分支与分组完整 |
| component | view、groups、nodes、edges，可选 parent_ref | 2–8 节点、≤10 边、连接度≤4；overview 只含 system/domain/endpoint，module_detail 单组并绑定父图 |
| activity | nodes、edges、narrative_step_ids | 顶层连续 S1…Sn 共5–10步，总数≤14，子步 Sx.y 必须有父步骤；唯一起点、至少一个终点、可达与可终止、条件分支完整 |
| deployment | groups、nodes、edges、boundary_triggers | 2–8 区、2–8 节点、≤10 边；物理端点、跨区关系与六种边界语义一致 |
| mindmap | nodes: {id,parent,label} | 2–32 节点、最多4层、每父≤6子；唯一根、无环、无孤立树、同级标签不重复 |

图例和详细关系放在 `explanation.md`，图内关系显示 E1…En；活动边显示条件，时序消息显示显式编号。说明文件是图包必需工件，防止短边标签丢失语义。标题也保存在说明与 brief 中。

## 布局

`layout.direction`：一般图 TB/LR/RL，架构固定 TB，思维导图 right/left/balanced；时序方向由参与者顺序决定。`layout.spacing` 缺省60，范围30–160；作为 flowchart/时序的间距建议值，并确定原生 mindmap 的节点位置间隔。Mermaid 可能保持分组内部的默认间距，不能仅凭参数改变就声称图面已改善；需查看实际输出，必要时改方向或拆图。原生 mindmap 渲染后保持节点尺寸，围绕根节点拉开位置和边，避免密集分支穿过第三方节点；SVG/PNG 使用该布局，直接在其他 Mermaid 查看器打开源码时可能采用其默认布局。简化标签或拆图必须保留需求，不可为通过预算删掉边。

## 时序

`numbering` 默认 interaction_mr（M1、R1…）；process_s 使用 S1、S1.1…，不混用，不自动编号。messages 的 arrow 支持 ->>、-->>、->、-->、-x、--x；note 最多500字符。短 note 位于目标参与者右侧，长 note 跨消息两端并折行。

blocks 使用 kind、label、start、end，位置从1开始。alt 还需 else_at、else_label。允许完整嵌套，拒绝交叉区间和跨越外层 else 的内块。消息顺序由数组决定。参与者可声明 group，分组必须存在且非空。

## 组件细化

`view: module_detail` 必须包含 `parent_ref: {path,sha256,diagram_id,node_id}`。path 相对输入 brief 所在目录且不能越界。hash 为父 overview brief 原始文件 SHA-256；验证父图本身、类型、diagram_id 与 node_id，复制到图包 `evidence/overview.json` 后再次复核。不能仅凭一个名称声称展开了某组件。

## 部署与活动

部署节点包含 kind、mode、network_id、chain_id。边界标记 cross_network/cross_chain 比较实际连接两端；online_offline 检查在线与离线的直接交接；hsm/manual_transfer/manual_handoff 检查节点类型。hybrid 不自动等价于 offline，必要时拆成明确的物理节点。关系说明保留边界触发原因。

活动 kind 为 start/action/decision/stop，判断节点至少两条不同非空条件边，普通动作唯一后继，终点没有出边。支持回路与提前终止；不支持隐含并行 fork/join，遇到该需求使用通用路径并显式验收并行语义。
