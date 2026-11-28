# Fixtures

本目录存放测试用的固定样例文件（fixtures）。

## 合法 fixtures（用于验证通过路径）

- `architecture-map.slide-ir.json` — 架构图示例（自建链 共识架构，16 元素，5 区域）
- `comparison-matrix.slide-ir.json` — 对比矩阵示例（4 链对比，9 元素，6 区域，含 KPI cards）
- `flow-diagram.slide-ir.json` — 流程图示例（API Gateway 生命周期，17 元素，5 区域）

## 问题 fixtures（用于验证 QA 检测）

- `connector-endpoint-test.slide-ir.json` — 测试连接器端点假阳性修复
- `text-overflow-test.slide-ir.json` — 测试文本溢出检测

## 失败 fixtures（用于验证 QA 正确拒绝）

- `bad-overlap.slide-ir.json` — 测试标签重叠、脚注碰撞、越界
- `bad-font.slide-ir.json` — 测试字号过低检测（正文 7pt、表格 7.5pt、脚注 8pt）

## P0 场景测试（输入与准出要求）

- `scenarios/p0/` — P0 五类模板的场景输入、页面契约和准出检查项。当前为"输入与准出要求"阶段，后续生成稳定 `slide-ir.json` 后再 promotion 到 `benchmarks/`。

## 用途

- 本地测试脚本（`tests/run.sh`）使用 fixtures 做轻量验证。
- Pipeline 集成测试使用 fixtures 作为回归基准。
