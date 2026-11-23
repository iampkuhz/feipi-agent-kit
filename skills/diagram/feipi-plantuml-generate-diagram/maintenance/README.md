# PlantUML 维护入口

运行合同由 `SKILL.md`、`references/render-rules.md` 和 `references/package-contract.md` 维护，本目录不参与客户端运行。

| 职责 | 实现与消费者 |
| --- | --- |
| 批次预检 | `scripts/preflight_renderer.py` 只读探测工作台提供的本机 HTTP 服务 |
| 本机 HTTP 渲染和错误分类 | `scripts/check_render.sh`；由预检和图包校验复用 |
| 单图编排和预览 | `scripts/run_mindmap.py`；真实 SVG 经 rsvg-convert 生成 PNG |
| 图包验证 | `scripts/validate_package.sh`；覆盖输入、布局、摘要及报告 |

定向回归：`python3 tests/test_check_render.py`。完整回归：`bash tests/run.sh`，需要已有本机渲染器；正向用例必须真实出图。macOS 和 Linux 运行结果分别记录，静态扫描不能代替跨平台实测。

新 Mac 回归关注工作台端口绑定、只读探测和真实中文图包。
