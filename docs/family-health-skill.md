# 家庭健康 Skill

`skills/authoring/feipi-health-maintain-family-records` 是唯一技能源码。实际家庭健康档案原位维护在 `~/Documents/life/家庭健康`；目录规则、模板与档案内容以该库为准，不复制进 Agent Kit。Codex 与 OpenClaw 只安装过滤后的运行副本。

## 使用

Codex 显式调用 `$feipi-health-maintain-family-records`，或直接要求归档家庭健康材料、更新成员进展、查询既往报告。

OpenClaw 使用 `/health`，在文字或附件说明中写明任务：

- `/health 归档这些体检报告`，附本地文件或来源链接。
- `/health 更新某成员上次不适的进展：……`，持续事件继续追加。
- `/health 查询某成员历年检查`，仅查询时不写档案。

`/health` 由 Telegram 自定义菜单和当前拥有者对话路由进入 Agent，再加载该 skill；不是独立执行插件。保留原消息与附件，不改动已有住宅、成长日记入口和访问权限。历史报告、临床判断和 AI 讨论分开记录；监测数据按需追加。菜单机制见 [OpenClaw slash commands](https://docs.openclaw.ai/tools/slash-commands)。

## 维护与测试

改源码后运行：

```bash
bash skills/authoring/feipi-health-maintain-family-records/tests/run.sh
bash skills/authoring/feipi-skill-govern/scripts/validate.sh skills/authoring/feipi-health-maintain-family-records
python3 scripts/harness/validate_registry.py
```

`tests/run.sh` 使用隔离合成库验证归属定位、重复附件、同名冲突、来源凭证拒绝、路径边界、损坏清单和完整性检查。`evals/cases.json` 保存报告整理、持续事件、偶尔监测、身份歧义、医学分析、材料指令隔离、只读查询、普通附件不冒充检查报告和来源不可访问等行为评估标准；结构校验不等于已执行全部模型评估。

调整安装器或工作台时另运行相关回归；改 OpenClaw 配置时运行 `make -C components/openclaw validate`。真实模型验收只对合成库执行写入，对实际健康库只读核验。运行日志、会话、真实档案快照只放私有状态目录，不进入 Git。

## 发布

先查看 `workbench diff`，再定向发布；保留其他客户端与未发布技能：

```bash
./workbench apply skills --agent codex --skill feipi-health-maintain-family-records
./workbench apply skills --agent openclaw --skill feipi-health-maintain-family-records
```

两次操作分别生成私有备份和回退命令，排除开发目录。以后从这里更新运行副本，不直接修改安装目录。

只有命令路由发生变化时才需要：

```bash
./workbench diff openclaw
./workbench apply openclaw
./workbench service openclaw restart --force
make -C components/openclaw runtime-check
openclaw skills info feipi-health-maintain-family-records --json
```

检查技能 eligible/modelVisible、实际资料库访问和 Telegram 命令菜单。CLI 通过 Gateway 的模型验收不等于真实 Telegram 附件端到端验收；没有实际测试的环节需保留说明。Codex 已打开的对话如未发现新 skill，可新开对话重新发现。
