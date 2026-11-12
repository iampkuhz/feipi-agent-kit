# feipi-skill-govern 源码维护

本目录只供维护治理 Skill 源码时读取，不安装到客户端。执行治理任务所需的规范仍在 `references/`。

先读 [术语与命名](terminology.md)，再根据改动读取以下真源：

| 内容 | 维护位置 |
|---|---|
| 触发与功能路由 | `../SKILL.md`、`../agents/openai.yaml` |
| 阶段功能契约、输入输出与消费者 | `../references/governance-process.md` |
| 正式交接记录与输入绑定 | `../references/governance-artifacts.md`、`../templates/governance-record.template.json`、`../scripts/check_delivery.py` |
| 技术、语义、链路验证及失败定位 | `../references/workflow.md`、`../references/quality-checklist.md` |
| 新建 Skill 与维护资料模板 | `../scripts/init_skill*.sh`、`../templates/` |
| 结构、维护资料与运行依赖校验 | `../scripts/validate.sh`、`../scripts/validate_resources.py` |
| 路径与双平台静态检查 | `../scripts/check_portability.py` |
| 确定性回归与独立 Agent 评估 | `../tests/run.sh`、`../tests/test_delivery.py`、`../evals/cases.json`、`../evals/README.md` |
| 安装与打包 | 仓库 `scripts/install_skills.sh`、`scripts/package_skill.py` |
| 全登记集合验收 | 仓库 `scripts/harness/validate_skill_layout.py` |

## 修改与验收

治理 Skill 可读取目标源码的维护资料；安装后的自身运行资源仍不能依赖本目录。校验器只允许明确的目标源码路径，不能按 Skill 名整体豁免维护依赖。

上表是职责与依赖导航；具体运行规则由对应规约维护，本入口不复制。新建与本次治理的维护资料、安装边界及验证要求见 `../references/development-layout.md`。

在本 Skill 根目录运行：

```bash
bash scripts/validate.sh . --require-maintenance
bash tests/run.sh
```

修改安装器时还要在仓库根运行：

```bash
python3 scripts/harness/validate_skill_layout.py
python3 -m unittest discover -s tests -p 'test_install_output.py'
python3 -m unittest discover -s tests/workbench
```

安装过滤和链接行为由 `scripts/package_skill.py` 实现、仓库布局测试覆盖；修改时沿上表的消费者核对。版本策略见 `../references/version-changelog-policy.md`，证据边界见 `../references/workflow.md`。
