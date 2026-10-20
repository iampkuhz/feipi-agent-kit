# 图包合同 v1

每个输出目录只服务一个图任务。成功目录包含：

| 文件 | 内容 |
|---|---|
| `brief.json` | 本次需求与布局的规范输入 |
| `diagram.drawio` | 可继续编辑的实际源文件 |
| `diagram.svg` / `diagram.png` | 同一次本地 draw.io 渲染结果与预览 |
| `render.json` | renderer 标识、源码哈希、实际 cell 包围盒/标签/路径 |
| `validation.json` | 阶段、状态、问题、渲染次数、耗时、产物哈希 |

状态为 `passed`、`failed` 或 `blocked`。`passed` 仅证明自动检查通过，`visual_review` 固定为 `pending`；Agent 必须实际查看 PNG 并在交付中说明视觉结论，不能自行把 JSON 改为已审。

renderer 阻塞时 `renderer_error` 与独立预检共用诊断格式：`status`、`reason`，按错误包含 `code`、`command`、`exit_code`、`stderr`（最多 2000 字符）和 `next_steps`。预检阻塞保留源文件且不增加 `render_attempts`；环境准备完成后可在原目录继续。

主入口没有外部 URL 或成功状态参数。客户端绕过环境代理、禁止重定向，验证本地 Podman 容器后才请求 renderer。请求前持久化次数，最多两次；服务故障不自动重试。只有 `stage=layout` 且源码发生修改允许一次修复。未变成功包可离线复用，文件变化/缺失或哈希不符即失败。

自动门禁：

1. brief 字段、ID 唯一性、分组无环、端点、坐标及预算。
2. XML 基本结构、节点/边/标签/方向/分组/坐标与 brief 完整对应；拒绝 DTD、外部资源、HTML、隐藏内容。
3. 真实 draw.io 几何：节点互不重叠，文字在节点内，子节点位于分组正文区域，连线不穿过其他节点和标签，标签不覆盖节点/其他标签。
4. SVG/PNG 非空、类型与尺寸合规，无 SVG 脚本、图片或外链；固定产物清单与 SHA-256。
5. 内置离线 verifier 重新读取实际文件、重新计算覆盖/几何检查和哈希。缓存也走同一 verifier。

边界：包围盒是保守近似，不证明任意曲线、菱形边缘、特殊形状和语义布局完美；视觉复核仍必需。不以 XML 可解析、HTTP 200 或存在 SVG 单独判定通过。修改后的业务语义和需求完整性由 Agent 对照原请求复核。
