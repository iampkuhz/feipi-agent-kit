# Mermaid 维护入口

运行契约由 `SKILL.md`、`references/runtime.md` 和 `references/package-contract.md` 维护，本目录不参与客户端运行。

| 职责 | 实现与消费者 |
| --- | --- |
| brief、图型与源码覆盖 | `scripts/model.py`；由 `scripts/run.py` 编排 |
| 固定 npm 依赖与共享缓存 | `scripts/prepare_runtime.py`；入口首次按需准备，检查模式只读 |
| 本地浏览器发现及 SVG/PNG | `scripts/render.mjs`；显式浏览器优先，复用系统 Chrome，禁止自动下载浏览器 |
| 几何、摘要与图包复核 | `scripts/package.py` 和 `scripts/review_package.py`；视觉复核后才可完成 |

离线回归入口为 `bash tests/run.sh`。平台验证需在 macOS 和 Linux 分别记录实际结果，不能用静态扫描替代。

新 Mac 回归案例：Homebrew cask 已安装 Google Chrome，但 PATH 没有 chrome 命令、Puppeteer 缓存为空时，`run.py` 必须自动发现系统应用并产出可复核 SVG/PNG；Python 依赖可用运行文档中的 uv 命令隔离准备。保留第一次失败报告，在原图包修复重跑，再人工检查中文和连线。
