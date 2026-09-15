# Benchmark 套件

## 概述

本目录包含 feipi-techreport-ppt-skill 的质量 benchmark。每个 benchmark 代表一个真实 CTO 技术汇报场景。

## 分层

### Smoke benchmark（CI 必跑）

| 名称 | 版式 | 说明 |
|------|------|------|
| `architecture-high-density` | architecture-map | 高密度架构图，20 个以内元素 |
| `flow-api-lifecycle` | flow-diagram | 5-7 步流程 |
| `comparison-competitive-matrix` | comparison-matrix | 4 对象 × 5 维度以内对比 |

### Full benchmark（release gate 前跑）

| 名称 | 版式 | 说明 |
|------|------|------|
| `roadmap-technical-delivery` | roadmap-timeline | 3-5 阶段交付路线图 |
| `metrics-dashboard` | metrics-dashboard | 3-5 KPI + 主图区域 |
| `decision-tree` | decision-tree | 判断分支 |
| `capability-map` | capability-map | 能力域分组 |
| `overload-should-split` | architecture-map | 故意过载，期望输出拆页建议 |

## 每个 benchmark 目录结构

```text
<benchmark-name>/
├── source.md              # 原始材料
├── page-contract.md       # Page Contract
├── slide-ir.json          # 结构化 Slide IR
└── expected-report.json   # 期望 QA 结果和评分基线
```

## 运行

```bash
# Smoke benchmark dry-run
node tests/run_benchmarks.js --dry-run --no-render

# Full benchmark
node tests/run_benchmarks.js --full --dry-run --no-render

# 单个 benchmark
node tests/run_benchmarks.js --filter architecture-high-density --dry-run
```

## 与 P0 场景的关系

本目录存放稳定回归用例（固定 `slide-ir.json` + `expected-report.json`）。P0 场景测试用例位于 `../../../evals/scenarios/p0/`，仅包含输入需求与准出检查项。当某个 P0 case 生成稳定的 `slide-ir.json` 并通过人工视觉评审后，会 promotion 到本目录。详见 `../../../evals/README.md`。
