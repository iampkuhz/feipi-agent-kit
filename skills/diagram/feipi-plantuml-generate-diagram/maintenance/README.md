# PlantUML 维护入口

运行合同由 `SKILL.md`、`references/render-rules.md` 和 `references/package-contract.md` 维护，本目录不参与客户端运行。

| 职责 | 实现与消费者 |
| --- | --- |
| 批次预检与有界启动 | `scripts/preflight_renderer.py`；默认只允许一次启动，`--existing-only` 禁止启动 |
| 本机 HTTP 渲染和错误分类 | `scripts/check_render.sh`；由预检和图包校验复用 |
| 单图编排和预览 | `scripts/run_mindmap.py`；真实 SVG 经 rsvg-convert 生成 PNG |
| 图包验证 | `scripts/validate_package.sh`；覆盖输入、布局、摘要及报告 |

定向回归：`python3 tests/test_check_render.py`。完整回归：`bash tests/run.sh`，需要已有本机渲染器；正向用例必须真实出图。macOS 和 Linux 运行结果分别记录，静态扫描不能代替跨平台实测。

新 Mac 回归关注首次启动命令的本机端口绑定、已有服务只读复用，以及真实中文图包。不要为验收重启用户原有容器。
