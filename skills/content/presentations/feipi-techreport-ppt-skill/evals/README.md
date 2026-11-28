# P0 场景测试体系

## 目录定位

P0 测试场景放在：

```text
evals/scenarios/p0/
```

该目录只存放**输入需求、结构化数据、页面契约和准出检查项**，不直接存放稳定回归用的 `slide-ir.json`。

稳定回归用例仍放在现有目录：

```text
tests/fixtures/benchmarks/
```

## 为什么不直接放入 benchmarks

`tests/fixtures/benchmarks/` 当前语义更接近"固定输入 + 固定 slide-ir + expected-report 的回归样例"。

P0 场景在早期会频繁调整：

- 同一需求可能测试多种布局；
- 同一模板可能有多个业务变体；
- 同一 case 可能反复生成、修复、评分；
- 准出标准会持续细化。

因此先将 P0 用例放入 `evals/scenarios/p0/`。当某个 case 的最佳 `slide-ir.json` 稳定后，再 promotion 到 `tests/fixtures/benchmarks/`。

## 推荐目录结构

```text
evals/scenarios/p0/
  README.md

  p0-01-complex-comparison-matrix/
    case-blockchain-capability-targets/
      source.md
      data.yaml
      page-contract.md
      expected-checks.md

  p0-02-layered-architecture/
    case-high-performance-evm-architecture/
      source.md
      data.yaml
      page-contract.md
      expected-checks.md

  p0-03-multi-role-interaction-flow/
    case-fhevm-hostchain-flow/
      source.md
      data.yaml
      page-contract.md
      expected-checks.md

  p0-04-stage-roadmap/
    case-financial-chain-5-stage-timeline/
      source.md
      data.yaml
      page-contract.md
      expected-checks.md

  p0-05-e2e-closed-loop/
    case-public-chain-integration-lifecycle/
      source.md
      data.yaml
      page-contract.md
      expected-checks.md
```

## 单个 case 文件职责

| 文件 | 作用 | 是否必需 |
|---|---|---|
| `source.md` | 模拟真实用户输入，保留自然语言需求 | 必需 |
| `data.yaml` | 将关键内容结构化，便于复用和生成多版本 | 必需 |
| `page-contract.md` | 页面级版式、内容密度、组件、风格约束 | 必需 |
| `expected-checks.md` | 准出检查项，分 Must / Should / Must Not | 必需 |
| `notes.md` | 记录失败样例、调优观察、人工判断 | 可选，默认 gitignore |
| `outputs/` | 临时生成结果，不进入稳定基线 | 可选，默认 gitignore |

## Promotion 到 benchmark 的条件

一个 P0 case 只有满足以下条件，才可以复制到 `tests/fixtures/benchmarks/`：

1. `source.md` 和 `page-contract.md` 稳定；
2. 已生成可接受的 `slide-ir.json`；
3. 已生成可接受的 PPTX；
4. `expected-report.json` 可复现；
5. 通过 `tests/run_benchmarks.js`；
6. 人工视觉评审认为该 case 能代表该模板的标准样例。

Promotion 后的目录建议：

```text
tests/fixtures/benchmarks/p0-01-blockchain-capability-targets/
  source.md
  page-contract.md
  slide-ir.json
  expected-report.json
```

## 准出标准分层

| 等级 | 含义 | 示例 |
|---|---|---|
| Must | 不满足即失败 | 必须原生表格；不能文字溢出；标题必须可读 |
| Should | 不满足可接受但要扣分 | 右侧说明区最好包含数据口径 |
| Must Not | 明确禁止 | 不得把大表格截图化；不得生成全页图片海报 |
