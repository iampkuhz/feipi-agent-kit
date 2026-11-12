# 源码维护、测试与行为评估布局

本文件只在创建、维护、评估或审计 skill 时读取。普通业务任务不得把开发目录加入上下文。

## maintenance

Skill 根目录的 `maintenance/` 是源码维护专用目录，包含非空 `README.md` 维护入口和 `terminology.md` 术语表。架构、设计说明按需保存，不创建空目录或无内容文档。业务执行必需的知识仍放 `references/`。

治理前先读取目标源码 `<target_skill>/maintenance/README.md` 与 `<target_skill>/maintenance/terminology.md`，明确业务对象和命名边界。新建或本次治理的目标补齐这两份资料；旧 Skill 暂不批量迁移。

普通运行资源（包括说明、参考、脚本、模板和配置）不得依赖源码维护资料。治理 Skill 可显式读取目标源码的维护资料；不能把自己的维护目录当作安装后的运行依赖。

## tests

`tests/` 保存确定性脚本测试、集成测试、fixture 和必要的 golden。统一入口是 `tests/run.sh`。测试可以调用 skill 的真实运行脚本；`scripts/`、`references/` 和其他运行资源不能依赖 `tests/`。

## evals

`evals/` 保存真实 Agent 行为用例、判定标准和基线。存在行为用例时使用 `evals/cases.json`；大型输入可放同目录下并使用相对路径引用。实际会话、模型输出、评分和比较报告写入仓库 `tmp/skill-evals/<skill-name>/`。

每条用例至少包含：

- `id`：稳定标识；
- `prompt`：用户可见请求；
- `expected`：必须出现的行为；
- `forbidden`：不得出现的行为。

涉及内容质量时，用原始材料独立制定判定标准，保留能暴露业务损失的输入。存在 fixtures 时注明准备方法；评估者只获得请求、当前 Skill 和原始材料，不提前看到预期答案或修复提示。实际产物、遗漏和验证覆盖由审阅者核对，不能用 cases.json 能解析或关键词匹配宣称语义通过。治理 Skill 的运行方法见其 `evals/README.md`。

## 加载与安装

- 普通 skill 的 `SKILL.md` 不引用 `tests/`、`evals/` 或开发命令。
- 只有 `feipi-skill-govern` 在治理态按需读取目标 skill 的开发目录。
- `scripts/install_skills.sh` 的链接、拷贝及打包内容递归排除 `maintenance/`、`tests/`、`evals/` 和 `node_modules/`，包括嵌套位置。链接模式实拷入口文件，只链接无需过滤的运行目录；需要过滤的父目录展开后再安装，确保客户端能发现 Skill 且不泄漏维护资料。
- 初始化默认创建维护入口、术语表和 `tests/run.sh`；只有确有 Agent 行为用例时才创建 `evals/`，不创建空目录。
- 新建与本次治理交付运行 `validate.sh <目标源码目录> --require-maintenance`。仓库级历史布局检查不带此参数，允许尚未治理的旧 Skill 暂缺维护目录；一旦存在该目录，两份维护资料都必须完整。
