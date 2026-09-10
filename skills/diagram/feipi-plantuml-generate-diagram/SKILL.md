---
name: feipi-plantuml-generate-diagram
description: PlantUML 唯一作图入口；在用户要求生成架构图、时序图、组件图、活动图、部署图、mindmap 思维导图或其他 PlantUML 图时触发，按图型 brief 生成并校验 diagram package。
---

# PlantUML 作图生成与校验

## 适用范围

- 根据自然语言或 YAML brief 生成可验证的 PlantUML 图包。
- 已注册图型：`architecture`、`sequence`、`component`、`activity`、`deployment`、`mindmap`。
- 未注册图型保留请求的 `diagram_type` 并进入 fallback；规则见 `references/type-routing.md` 与 `references/fallback-mode.md`。
- 非 PlantUML 输出不使用本 skill；修改 skill 本身使用 `feipi-skill-govern`。

## Mindmap 单图最短路径

1. 根据 `assets/templates/types/mindmap-brief.yaml` 写 brief。节点为 `{id, parent, label}`，根的 parent 为 `""`。单图沿用 `diagram_id: D1`；自定义图 ID 用小写连字符，节点 ID 可用下划线。
2. 默认 `layout.direction: right`；用户明确要求时选 `balanced` 或 `left`。预算为 2–32 个节点、含根最多 4 层、每节点最多 6 个子节点。
3. 在 skill 目录执行以下入口；其他工作目录用脚本的实际安装路径。输出目录用于本次首次生成：

```bash
python3 scripts/run_mindmap.py --brief brief.yaml --out-dir package
```

4. 入口内部完成输入校验、一次预检、源码生成、图包验证及 PNG 预览。正常任务无需分别调用内部脚本。配置与依赖说明见 `references/mindmap-execution.md`；手写语法与样式调整见 `references/mindmap-authoring.md`。
5. 查看返回的 `paths.preview`，确认中文、层级、方向与无截断，再交付源码和 SVG 链接。`visual_review: pending` 表示仍需视觉复核。失败按返回的 `stage/reason/issues` 处理，不自行枚举替代工具。

## 其他图型与已有图包

1. 从 `assets/templates/types/` 选择对应 brief；图型边界与预算见 `references/diagram-type-profiles.md`。先完成 schema、语义和预算校验，输入失败不调用 renderer。
2. 每批次执行一次 `scripts/preflight_renderer.sh`，后续图复用回执的 `renderer_url`。
3. 按 profile 生成源码，调用 `scripts/validate_package.sh --diagram-type <type> --brief <brief> --diagram <puml> --out-dir <package> --server-url <renderer_url>`。
4. `sequence` 默认 `interaction_mr`，专利流程使用 `process_s`。已有 mindmap 的定点修复也用该验证入口；不要重新运行生成器覆盖人工修改。
5. 未变成功包显式使用 `--reuse-valid-package`；brief、diagram、父 brief、profile 或渲染合同变化时缓存失效。合同细节见 `references/package-contract.md`。

## 统一质量与失败边界

- 输出至少包含 `diagram.puml`、`validation.json`；只有真实渲染成功才有可交付的 `diagram.svg`。mindmap 定界符为 `@startmindmap/@endmindmap`，其他现有图型为 `@startuml/@enduml`。
- brief/schema、覆盖、布局、真实 SVG、artifact hash 与源码 metrics 的校验必须保留；`validate_package.sh` 内置 verifier，不重复手动调用。
- 默认本地端口读取 `AGENT_PLANTUML_SERVER_PORT`，缺省 8199；显式 `--server-url` 也只接受 loopback。规则见 `references/render-rules.md`。
- 预检首次不可用时，仅默认 8199 地址允许一次固定 Podman 启动并复检一次；仍不可用即 blocked。禁止继续启动、杀死、重启或排查 renderer/proxy 进程。
- 明确的连接权限错误优先返回 `render_access_denied`，不启动 Podman、不复检。报告“访问被拒绝，可能受沙箱或系统权限限制”，不能断言服务未启动；普通连接失败或超时也不能直接断言沙箱限制。脚本不能自行提权，遵循宿主权限策略；详情见 `references/render-rules.md`。
- 每图首次渲染一次，仅 syntax/coverage/layout 失败允许定点修复一次；总渲染上限两次。未修改失败图不重复运行，不通过更换目录重置计数。
- brief/over_budget、renderer、contract/retry_limit 失败停止；视觉问题交给 reviewer，不自动进入渲染循环。
- 静态校验与 renderer 冲突时转工具缺陷处理；维护与合同规则见 `references/package-contract.md`。正向测试必须有真实渲染证据，mock 通过不能替代。
