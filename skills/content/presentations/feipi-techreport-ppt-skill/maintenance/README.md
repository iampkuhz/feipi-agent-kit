# PPT 维护入口

运行合同以 `SKILL.md`、`references/`、`design-system/` 和 `schemas/` 为准，本目录不参与客户端运行。

| 职责 | 实现与消费者 |
| --- | --- |
| 主生成与验收 | `scripts/generate_pptx_pipeline.js`，复用 compiler、adapters 与 QA |
| 锁定 npm 依赖 | `scripts/prepare_runtime.py` 和 `helpers/dependencies.js`，依赖放在本机共享缓存 |
| 开发演示 | `tests/generate_demo_deck.js`，只消费 `tests/fixtures/benchmarks/`，不进入安装副本 |
| 多页预览 | `scripts/render_pptx.sh`，LibreOffice 转 PDF、Poppler 逐页转 PNG；实际页数与 PPTX 一致，只登记本轮工件 |
| 回归 | `bash tests/run.sh`，覆盖合同、P0、benchmark、原生 PPTX 及演示完整性 |

真实使用验收应执行 review pipeline、查看实际渲染页面并检查原生可编辑对象。静态、离线或 QuickLook 通过不能替代 PowerPoint 编辑回环；各平台实测分别记录。
