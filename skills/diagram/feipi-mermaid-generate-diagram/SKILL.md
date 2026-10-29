---
name: feipi-mermaid-generate-diagram
description: 生成或修改 Mermaid 架构图、时序图、组件图、活动图、部署图、思维导图及其他 Mermaid 图，交付经过真实渲染与质量检查的源码图包；用户指定 PlantUML 或 draw.io 时不使用。
---

# Mermaid 作图与图包验收

## 适用范围与输入

- 根据用户需求提炼图的目的、节点、关系、边界与显示文本，写成 JSON 或 YAML brief。只问会改变图意的缺失信息；不编造系统、接口或流程。
- 六个结构化图型：`architecture`、`sequence`、`component`、`activity`、`deployment`、`mindmap`。从 `assets/examples/<type>.json` 复制可运行示例并替换需求；预算与字段见 [图型说明](references/profiles.md)。
- 类图、状态图、ER、甘特等其他 Mermaid 图保留原 `diagram_type`，按 [通用路径](references/fallback.md) 提供源码。文字匹配不能代表语义验收。
- 用户指定其他输出格式时使用对应 skill；修改本 skill 使用 `feipi-skill-govern`。

## 最短执行路径

在 skill 目录执行，其他目录使用脚本实际安装路径：

```bash
python3 scripts/run.py --brief brief.yaml --out-dir package
```

1. 第一次使用先按 [本地运行](references/runtime.md) 准备固定依赖。入口不会在渲染失败后自行联网安装或更换 renderer。
2. 入口依次做 schema、语义、预算、源码覆盖、一次浏览器预检、真实 SVG 渲染、同图 PNG 预览、几何检查及独立图包复核。输入失败不启动浏览器。
3. 查看返回的 `paths.preview`，检查中文、层级、关系、分支和密集区域，确认无重叠、错归属、裁切。自动几何检查不能代替视觉检查。
4. `review_required` 表示技术检查通过，仍未完成验收。实际看图后记录具体结论：

```bash
python3 scripts/review_package.py package --decision pass --notes '中文清晰，关系归属与分支一致，无裁切或遮挡'
```

有问题用 `--decision fail`，不得为了绿色状态直接填 pass。通用图还须逐项核对语义并加 `--semantic-reviewed`。

5. 仅 `validation.json.final_status=success` 可作为完成。交付 `diagram.mmd`、`diagram.svg`、`diagram.png`、`explanation.md` 与验证状态；链接到实际文件。

## 图型选择与显示文本

- 架构、组件、活动、部署使用 `flowchart` 的稳定分组和关系语法；这四种是业务 profile 名称，不冒称 Mermaid 原生 UML 图型。
- 时序用 `sequenceDiagram`，支持参与者分组、明确编号、消息 note、嵌套且不交叉的 alt/opt/loop/critical。活动图用显式条件边，不能把文本顺序当作控制流。
- 思维导图默认 `right`，可选 `left` 或 `balanced`。前两种用 flowchart 保留单根树与方向；均衡用原生 `mindmap`。如用户指定原生语法，应选 balanced 并告知布局由 Mermaid 决定。
- 标签写原始文字，包含引号、文件路径、括号和换行都不预转义。生成器转义语法敏感字符并按显示宽度换行；关系 ID 与结构语法单独处理。
- 源码只接受本 profile 生成的结构，允许空行、缩进和普通注释。通过 brief 的关系、方向和 `layout.spacing` 调整图；已有任意 Mermaid 源码按通用路径处理，不强塞进结构化 profile。

## 定点修改、复用与失败

- 同一图一直使用同一输出目录。结构化图修改 brief 后重跑入口；通用图或检查现有源码添加 `--diagram diagram.mmd`。
- 输入、代码合同和图包均未改变时显式加 `--reuse`。先核对旧包所有工件；复用不启动浏览器，报告区分历史与本次计数。
- 每图最多两次真实渲染：首次一次，定点修复一次。未修改失败输入不重试；禁止换目录重置次数。预检失败不消耗图的渲染次数。
- 输入、超预算、父图身份、依赖/浏览器或合同失败立即停止，报告具体层次。权限失败不能据此断言 renderer 不存在；不修改系统权限，不管理其他服务进程。
- 真实渲染后布局失败保留 brief、源码和诊断，移除不能交付的图；按坐标/文字定位后调整一次。若检测能力不足或人工视觉失败，说明未验收，不虚报通过。
- 入口的 exit 0 也可能是 `review_required`；消费方必须读取最终状态。报告、缓存、路径和计数合同见 [图包合同](references/package-contract.md)。
