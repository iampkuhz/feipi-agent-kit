# draw.io 维护入口

运行合同由 `SKILL.md` 和 `references/` 维护，本目录不参与客户端运行。

| 职责 | 实现与消费者 |
| --- | --- |
| 图包编排与布局 | `scripts/run_diagram.py` 和 `scripts/core.py` |
| 本机 Podman 身份预检及 HTTP 请求 | `scripts/renderer.py`；禁止远端 engine，`--existing-only` 不启动 |
| 首次准备 | `scripts/prepare_renderer.py` 发现仓库的 `tools/diagram/drawio/`，复用固定源码构建 |
| 独立产物校验 | `scripts/verify_package.py`，校验摘要、几何和报告 |

离线回归：`bash tests/run.sh`；真实本机回归：`bash tests/run.sh --live`。正向真实图包应产出可编辑 XML、SVG 和 PNG，再实际看图；不要为验收重建或停止已有容器。macOS/Linux 真实运行分别记录，复用旧机 renderer 不证明新机冷启动。
