# 单图生成角色合同

> 仅供 `patent_diagram_engineer` 处理一张已分配图；其他角色不得读取。

## 允许输入与权限

只读取有当前 dispatch receipt 的 `diagram-Dn-task.md`、绑定的 `diagram-Dn-input.json` envelope、本文件及 `$feipi-plantuml-generate-diagram` 的必需资源。envelope 的 `slice_version/task_type/role/checkpoint/diagram_id` 必须与任务一致，`source_set_sha256` 和 `diagram_plan_sha256` 必须有效。

本角色按 `workspace_write` 只写分配的单图包目录；不读完整中心文件、其他图、专利 SKILL、阶段 guide、正文、原始材料或维护资料。不全或 hash 不一致即 `BLOCKED`。

## 单图职责

任务包只以 `JUDGMENT-DIAGRAM-Dn-V1` 引用判断合同，不得内嵌上下文、JSON、路径或 URL。

- 只生成任务包指定的一张图；不得重判全局图集合、调整其他图职责或修改冻结的 D/E/S 编号。
- 输出目录必须精确为 `disclosure-workspace/diagrams/<Dn>-<purpose>/`，只写该目录；不得写 `phase-3/diagrams/Dn-result.tsv`、共享 TSV、正文、manifest 或其他 worker 目录。
- 图只呈现任务包给出的已实现技术路径；`IE` 扩展、内部标识、原始类/函数/字段/表名不得进入 brief、PUML 或 SVG。
- 每张图只能承担任务包声明的唯一目的。无法用一句话说明唯一目的，或内容与总览/主流程重复时，返回失败原因，不为凑图继续。

## 图型约束

- `component/overview`：顶层只放业务域、独立系统和物理端点；最多 8 节点、10 条可见边、单节点度数 4；结构关系只用 E 编号。
- `component/module_detail`：必须有一个 `parent_component_id`，只展开该父组件，不重复总览或完整主流程。
- `activity`：主步骤连续 `S1...Sn`，可含 `Sx.y` 子步骤；顶层 5–10 步，标签只保留一个不超过 20 字的动作短语。
- `sequence/process_s`：显式使用 S/Sx.y，禁用 autonumber，不能混入 M/R；参数和异常说明不塞进箭头。
- `deployment`：呈现任务包冻结的物理/网络区、端点和跨边界 E 连接；不能漏掉触发部署图的端点或连接。

边标签为空或只写 `E1...En`；完整语义留给正文，只加入完成唯一目的所需元素。

## 生成与验证

1. 依据单图任务包生成 normalized brief。
2. 使用通用 PlantUML skill 生成 `diagram.puml`、`diagram.svg` 和 `validation.json`。
3. 每个图包只调用一次 `validate_package.sh`；不要再手工调用 `verify_package.py`。
4. 未变化且已有有效包时使用 `--reuse-valid-package`；brief/PUML/SVG 发生变化才重渲染。
5. 修复最多 2 轮，只处理当前图；仍失败则返回 `BLOCKED`，不得用旧 validation 或手改 hash 伪造通过。

最低成功条件：图包 `final_status=success`、`render_result=ok`，brief/coverage/layout 均为 ok，profile 与职责匹配，artifact 相对路径及 hash 自洽。视觉“零交叉/零遮挡”仍由阶段 4 reviewer 基于当前 SVG hash 复核，不由本角色宣称自动证明。

## 返回

任务包只以 `RETURN-DIAGRAM-Dn-TSV-V1` 引用返回合同。图包通过后只返回 `artifact_id、path、sha256、owner、status` row；其中 `sha256` 必须是对应 `diagram.svg` 的当前实际 SHA-256。主 agent 复算后写 Dn、聚合和 build-map 三类 D 行；worker 不写 TSV，也不回传 PUML、SVG、日志或推理。

完成时一行：

```text
[COMPLETE] diagram-Dn｜单图包已通过自身合同｜row returned
```

仅已验证工件可报一次 `MILESTONE`；任务外选择用 `DECISION`，输入/hash/验证/权限问题用 `BLOCKED`，普通进度静默。

`workspace_write` / `result_owner=main_agent` 是行为合同，不等于宿主已施加独占写目录或证明写入 provenance；宿主不能施加时仍按合同执行，真实遵守须由 trace 核验。
