# Release Gate（发布门禁）

## 定位

Release Gate 是 Presentation Compiler 第二阶段的最终交付验证。
它确保所有工程能力就绪，可以高效产出高质量、可编辑的 PPT。

## 运行方式

```bash
# 默认模式：允许 static-only pipeline
bash tests/release_gate.sh

# 严格模式：要求 pptxgenjs + LibreOffice 均可用
bash tests/release_gate.sh --strict
```

## 退出码

- `0`: Gate 通过（default 模式下 static-only 也算通过）
- `1`: Gate 有 FAIL 项（strict 模式下缺少依赖必定 exit 1）

## 检查项

| # | 检查 | 说明 |
|---|------|------|
| 1 | Runtime Doctor | 验证 Node.js、pptxgenjs、LibreOffice 等运行时能力 |
| 2 | Test Suite | 运行 `tests/run.sh`，验证结构、术语、Static QA |
| 3 | Benchmark Dry-Run | 验证所有 benchmark 可解析无错误 |
| 4 | Quality Scoring | 运行 benchmark scoring，分数 >= 85 |
| 5 | PPTX Post-Check | 检查产物完整性、placeholder 残留、路径泄漏 |
| 6 | Residue Search | 搜索 placeholder/lorem/xxxx 文本残留 |
| 7 | Cache System | 验证缓存系统可用 |
| 8 | Script Inventory | 确认所有预期脚本存在 |

## 通过标准

- 所有 8 项检查 PASS（或在缺依赖时正确 SKIP）。
- 无 `FAIL` 项。
- Benchmark 平均分 >= 85（基于 `QUALITY_RUBRIC.md`）。

## 输出

- `tmp/ppt-skill-v2-run/release/default/release-report.md` — 默认模式可读报告
- `tmp/ppt-skill-v2-run/release/default/release-report.json` — 默认模式结构化报告
- `tmp/ppt-skill-v2-run/release/strict/release-report.md` — 严格模式可读报告
- `tmp/ppt-skill-v2-run/release/strict/release-report.json` — 严格模式结构化报告

> default 和 strict 输出隔离到不同子目录，防止并发运行互相覆盖。

## 缺依赖环境

在缺少 `pptxgenjs` 或 LibreOffice 的环境中，Release Gate 应：
- 输出结构化的 SKIP/FAIL 状态，而不是误报成功。
- 说明缺失的依赖和安装建议（与 `scripts/README.md` 一致：`cd skills/authoring/feipi-techreport-ppt-skill && npm ci`）。
- 仍通过所有不依赖这些组件的检查。
- **Strict 模式**下缺少依赖时，必须 FAIL 且退出码非 0。

## 与 QA Gates 的关系

- QA Gates（`references/qa-gates.md`）定义质量检查规则。
- Release Gate 是端到端的交付验证，包含 QA Gates 的结果。
- Release Gate 通过后，可以认为 skill 达到可交付状态。
