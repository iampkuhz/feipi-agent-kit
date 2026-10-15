---
name: feipi-drawio-generate-diagram
description: 用于生成或修改 draw.io（diagrams.net）架构图、流程图等可编辑图表；在用户要求 draw.io 或 .drawio 文件时使用，通过 Podman 本地服务渲染并校验图包。
---

# draw.io 作图与本地校验

## 适用范围

- 从自然语言整理 brief，生成可编辑 `.drawio`、SVG、PNG 与验证报告。
- 修改已有 draw.io 时保留业务节点 ID、标签、分组和连线方向；支持单页压缩/未压缩 XML 与裸 `mxGraphModel`。
- 按图意选择节点、分组和路由，可表达架构、组件、部署、流程和树状图；`diagram_type` 用于记录用户图意，不宣称验证 UML 专属语义。
- 用户指定 PlantUML 时使用对应 skill；本 skill 不把 draw.io 转成 PlantUML。

## 最短执行路径

1. 用 `assets/brief.example.json` 整理需求；字段与布局规则见 `references/authoring.md`。简单任务直接推导，不要求用户手填 JSON。
2. 在 skill 目录运行；安装后从其他目录执行时用脚本的真实路径：

```bash
python3 scripts/run_diagram.py --brief brief.json --out-dir package
```

3. 已有文件加 `--diagram existing.drawio`；brief 中记录实际节点、标签、坐标、分组与边。入口验证已有文件，不会重新生成覆盖它。
4. 脚本执行输入/覆盖校验、Podman 本地预检、真实 SVG/PNG 渲染、渲染几何检查和独立产物复核。成功后查看 `package/diagram.png`，确认中文可读、语义完整、分组清楚和连线归属；自动报告的 `visual_review: pending` 不能当成视觉验收已完成。
5. 交付 `.drawio`、SVG、PNG、`validation.json` 链接，说明自动校验及实际视觉复核结果。图包失败时保留报告和源文件，不能把旧图或仅有 XML 的结果当成渲染成功。

## 本地环境

- 主机需要 Python 3.10+ 与 Podman；不使用 Docker CLI、宿主 draw.io Desktop、在线编辑器或远程导出服务。
- 环境未准备时读取 `references/local-renderer.md`，按仓库工具说明执行一次 `prepare` 和 `up`。依赖下载只发生在准备阶段；渲染浏览器禁止外部 HTTP 请求。
- 只访问 `http://127.0.0.1:${AGENT_DRAWIO_SERVER_PORT:-8200}`；也验证 Podman 默认连接、镜像、容器标签和 loopback 端口绑定。
- 普通作图最多启动一次已经准备好的 `feipi-drawio` 容器；不会拉镜像、建虚拟机、重建/杀死容器。`--existing-only` 禁止启动。批次可先用 `scripts/preflight_renderer.py --existing-only` 预检，逐图执行时沿用已有服务。
- renderer 不可用返回 `blocked`，保留实际错误，不把权限错误推断成服务未启动，不尝试其他端口/代理或在线兜底。

## 质量门禁与修复

- 源文件必须覆盖 brief 的全部节点、标签、分组、连线与方向；含外部资源、HTML 标签渲染、隐藏元素或多页时需先规范化，不能静默删掉内容。
- 实际 draw.io 渲染几何检查：节点重叠、文字溢出、分组越界、连线穿过节点/其他文字、标签重叠。图形边框按包围盒保守检查，弯曲线/特殊形状仍需视觉复核。细节见 `references/package-contract.md`。
- 输入错误在请求 renderer 前返回。真实布局失败可根据报告定点修复一次，同一图包总共最多两次渲染；更新 brief 的布局与源文件保持一致。失败源码未改不得重跑，不换目录重置预算。
- 成功且未变图包加 `--reuse-valid-package`，仅离线复核哈希和几何；输入改变则拒绝复用。正常成功流程已内置 verifier，无需再手工运行。
- 离线审计已有图包可用 `python3 scripts/verify_package.py package`；报告通过后不要修改产物或手写通过状态。
