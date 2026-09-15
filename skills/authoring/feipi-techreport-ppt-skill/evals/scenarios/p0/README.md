# P0 单页 PPT 场景测试

本目录存放 P0 模板的场景输入、结构化数据、页面契约和准出检查项。

它不是稳定回归基线目录。稳定基线仍放在：

```text
tests/fixtures/benchmarks/
```

## P0 模板

| P0 ID | 模板 |
|---|---|
| P0-01 | 复杂多对象对比矩阵页 |
| P0-02 | 分层架构 / 组件结构图页 |
| P0-03 | 多角色交互流程 / 泳道流程页 |
| P0-04 | 阶段演进 Roadmap 页 |
| P0-05 | 端到端链路闭环页 |

## Case 使用方式

每个 case 包含：

```text
source.md
data.yaml
page-contract.md
expected-checks.md
```

建议执行流程：

1. 读取 `source.md`，理解真实用户需求；
2. 读取 `data.yaml`，提取结构化内容；
3. 读取 `page-contract.md`，确定模板与版式；
4. 生成 `slide-ir.json`；
5. 编译 PPTX；
6. 根据 `expected-checks.md` 做准出检查；
7. 若结果稳定，再 promotion 到 `tests/fixtures/benchmarks/`。
