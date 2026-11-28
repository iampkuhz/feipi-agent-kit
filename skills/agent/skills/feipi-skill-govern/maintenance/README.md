# feipi-skill-govern 源码维护

本目录只供维护治理 Skill 源码时读取，不安装到客户端。执行治理任务所需的规范仍在 `references/`。

先读 [术语与命名](terminology.md)，再根据改动读取以下真源：

| 内容 | 维护位置 |
|---|---|
| 触发与功能路由 | `../SKILL.md`、`../agents/openai.yaml` |
| 阶段功能契约、重构退出、模块拆分与消费者 | `../references/governance-process.md` |
| 正式交接记录与输入绑定 | `../references/governance-artifacts.md`、`../templates/governance-record.template.json`、`../scripts/check_delivery.py` |
| 技术、语义、链路验证及失败定位 | `../references/workflow.md`、`../references/quality-checklist.md` |
| 通用 Token 计数与迁移分组调用 | `../references/workflow.md`、`../scripts/count_tokens.py`、`../scripts/count_review_tokens.py` |
| 新建 Skill 与维护资料模板 | `../scripts/init_skill*.sh`、`../templates/`；默认图来自仓库图库 |
| 正式校验入口和结构 | `../scripts/validate.sh` |
| Python 校验入口、维护资料和运行资源边界 | `../scripts/validate_resources.py`、`../tests/test_resources.py` |
| 宿主调用策略、徽章、图标和图像资源 | `../scripts/validate_host_metadata.py`、`../tests/test_host_metadata.py` |
| 图标检索、版本发现及新图稿 | `../references/skill-icons.md`、`../scripts/skill_icon_catalog.py`、`../scripts/discover_cursor_icons.py`、`../scripts/render_skill_icon.py` |
| 迁移和候选审阅 | `../references/migration-policy.md`、`../references/manual-review.md`、`../scripts/check_migration.py`、`../scripts/review_skill.py` |
| 共享入口写法、元数据保留和中文复核 | `../references/entry-writing.md`、`../references/frontmatter-policy.md` |
| 路径与双平台静态检查 | `../scripts/check_portability.py` |
| 确定性回归与独立 Agent 评估 | `../tests/run.sh`、`../tests/test_delivery.py`、`../evals/cases.json`、`../evals/README.md` |
| 安装与打包 | 仓库 `scripts/install_skills.sh`、`scripts/package_skill.py` |
| 全登记集合验收 | 仓库 `scripts/harness/validate_skill_layout.py` |

## 修改与验收

治理 Skill 可读取目标源码的维护资料；安装后的自身运行资源仍不能依赖本目录。校验器只允许明确的目标源码路径，不能按 Skill 名整体豁免维护依赖。

上表是职责与依赖导航；具体运行规则由对应规约维护，本入口不复制。新建与本次治理的维护资料、安装边界及验证要求见 `../references/development-layout.md`。

### 修改校验规则

仓库全量校验、治理 Skill 自测和安装副本都从 `validate.sh` 进入。它调用 `validate_resources.py`，后者调用宿主模块并检查开发目录边界。新增 Python 校验由这条调用链接入。

- 宿主字段变化时，联动更新 `frontmatter-policy.md` 和宿主模块。模板需要提供该字段时，同步修改初始化模板。回归覆盖有效配置、逐宿主缺项，以及已有跨宿主调用策略冲突。
- 源码维护目录和分发边界变化时，更新资源校验，并对照 `scripts/package_skill.py` 的安装过滤规则。改动了模块依赖时，运行隔离安装回归，从安装副本执行正式入口。
- 共享校验改动同时跑仓库全量校验，覆盖 registry 中已有 Skill。

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

安装过滤和链接行为由 `scripts/package_skill.py` 实现、仓库布局测试覆盖；修改时沿上表的消费者核对。仓库级验收命令从目标仓库 `AGENTS.md`、构建入口或 CI 配置确认，不凭记忆假设路径。版本策略见 `../references/version-changelog-policy.md`，证据边界见 `../references/workflow.md`。
