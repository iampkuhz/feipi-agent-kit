# 测试与行为评估布局

本文件只在创建、维护、评估或审计 skill 时读取。普通业务任务不得把开发目录加入上下文。

## tests

`tests/` 保存确定性脚本测试、集成测试、fixture 和必要的 golden。统一入口是 `tests/run.sh`。测试可以调用 skill 的真实运行脚本；`scripts/`、`references/` 和其他运行资源不能依赖 `tests/`。

## evals

`evals/` 保存真实 Agent 行为用例、判定标准和基线。存在行为用例时使用 `evals/cases.json`；大型输入可放同目录下并使用相对路径引用。实际会话、模型输出、评分和比较报告写入仓库 `tmp/skill-evals/<skill-name>/`。

每条用例至少包含：

- `id`：稳定标识；
- `prompt`：用户可见请求；
- `expected`：必须出现的行为；
- `forbidden`：不得出现的行为。

## 加载与安装

- 普通 skill 的 `SKILL.md` 不引用 `tests/`、`evals/` 或开发命令。
- 只有 `feipi-skill-govern` 在治理态按需读取目标 skill 的开发目录。
- `scripts/install_skills.sh` 的链接与拷贝模式都排除 skill 根目录下的 `tests/` 和 `evals/`。
- 初始化默认创建 `tests/run.sh`；只有确有 Agent 行为用例时才创建 `evals/`，不创建空目录。
