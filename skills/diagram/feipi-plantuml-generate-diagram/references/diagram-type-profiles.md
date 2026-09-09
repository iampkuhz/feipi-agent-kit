# Diagram Type Profiles

## 概述

每个 typed profile 维护自己的 schema、模板、覆盖规则和布局规则。统一 skill 通过 profile 注册表路由到对应逻辑。

## 已注册 profile

### architecture

- Brief schema：`assets/validation/types/architecture-brief.schema.json`
- Brief template：`assets/templates/types/architecture-brief.yaml`
- 覆盖校验：检查层名、组件 id、流程编号全部落图；额外组件 alias 被拦截
- 布局校验：纵向布局，`top to bottom direction`，package 数量，legend
- 规模预算：层 3–6、组件 3–12、流程 1–16、每层最多 5 个组件；标签受显示宽度约束

### sequence

- Brief schema：`assets/validation/types/sequence-brief.schema.json`
- Brief template：`assets/templates/types/sequence-brief.yaml`
- 编号策略：缺省 `interaction_mr` 保持 `M/R`；`process_s` 接受 `Sx/Sx.y`，禁止混用及 `autonumber`
- 覆盖校验：检查参与者 id、消息编号全部落图；额外消息被拦截；separator 数量校验
- 布局校验：box/separator 结构、编号策略、`box` 与 `left to right` 互斥，`separator` 关键字禁用
- 规模预算：参与者 2–8、消息 1–20、group 最多 5；标签受显示宽度约束

### component（已注册）

- 支持 `overview` 与 `module_detail`；后者必须声明唯一 `parent_component_id` 与 `parent_component_ref`
- `parent_component_ref` 通过安全相对路径、overview brief hash、diagram id 与节点 id 共同绑定；细化图只能使用一个分组，不能仅凭非空字符串声称父组件
- `overview` 顶层只允许业务域、独立系统与物理端点
- 节点最多 8、可见关系最多 10、单节点连接度最多 4；边标签只允许为空或 `E1...En`

### activity（已注册）

- 顶层步骤使用连续 `S1...Sn`，允许 `Sx.y` 子步骤且父步骤必须存在
- 顶层步骤 5–10 个，标签只写单一动作短语
- `narrative_step_ids` 必须与图中步骤集合一致，孤立或额外步骤失败
- 使用 `start`、`:Sx 动作;`、`if (...) then (标签)`、`else (标签)`、`endif`、`stop/end`；使用默认纵向布局，不写通用方向声明；`include_legend=true` 时 legend 必须真实落图
- 条件标签进入对应转移签名；`else` 恢复条件入口，`endif` 合并仍可继续的分支，结束分支不得连接到后续步骤
- 未实现的控制流或不完整的条件结构必须显式拒绝，不能退化为把所有步骤相邻连接；样例的静态通过必须同时由真实 renderer 验证

### deployment（已注册）

- 建模物理区、网络区、在线/离线端点、HSM 与人工交接点
- 至少包含一个物理端点和一条跨区连接；结构关系使用 `E1...En`
- `boundary_triggers` 六项必须与实际端点/连接语义双向一致：网络 id、链 id、在线/离线连通域、HSM、人工摆渡点、人工交接点既不能漏报也不能虚报

### mindmap（已注册）

- Brief schema/template：`assets/validation/types/mindmap-brief.schema.json`、`assets/templates/types/mindmap-brief.yaml`
- 只建模 `nodes: [{id, parent, label}]` 单根树，自动派生边与深度；`layout.direction` 默认为 `right`；显式支持 `balanced/left`
- 单图入口 `scripts/run_mindmap.py` 串联预检、生成、图包验证与 PNG 预览；内部 `scripts/generate_mindmap.py` 生成带原生样式的 arithmetic 源码；支持手写 OrgMode；定界符为 `@startmindmap` / `@endmindmap`
- 校验唯一根、ID/父引用、循环、同级标签、路径覆盖、左右归属及真实源码 metrics；预算为 2–32 节点、含根最多 4 层、每节点最多 6 子节点
- 默认白底、浅色分支、深色文字、自动折行；布局规则独立于架构图；完整用法与限制见 `mindmap-authoring.md`

## 待扩展 profile

以下 profile 已预留，待后续通过 `references/expansion-playbook.md` 流程接入：

- `class` - 类图
- `state` - 状态图
- `usecase` - 用例图
- `gantt` - 甘特图
- `wireframe` - 线框图

## Profile 接口约定

每个 typed profile 必须实现以下接口（脚本层面）：

1. **brief 校验**：`lib/validate_brief_cli.py <brief.yaml> --schema <schema.json>`（由 `validate_package.sh` 调用）
2. **覆盖校验**：`check_coverage.py --type <type> --brief <brief.yaml> --diagram <diagram.puml>`
3. **布局校验**：`lint_layout.sh --type <type> <diagram.puml>`
4. **渲染校验**：统一使用 `check_render.sh`

所有 package 使用 `validation.json` v1.2：除路径、hash、metrics 与 timing 外，还必须记录 `failure_class`、`repairable`、`issues`、`attempt_index`、`max_render_attempts` 和 `attempts_remaining`。规范化 PlantUML hash 先把换行统一为 LF，删除行尾空白及首尾空行，再补一个末尾换行。`metrics` 必须从实际 PUML 重算，不能抄 brief；typed success 必须同时绑定 brief、diagram、当前 SVG，三项检查为 `ok` 且 renderer 非空。路径必须是包内安全相对路径，顶层字段与 artifact 记录双向一致。
