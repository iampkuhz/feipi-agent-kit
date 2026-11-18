# 家庭健康 Skill

Codex 和 OpenClaw 加载同一 Skill 的运行副本。家庭健康档案原位维护在 `~/Documents/life/家庭健康`，目录规则、模板和档案内容也以该库为准。 [Skill 源码](../skills/authoring/feipi-health-maintain-family-records/SKILL.md)

## 使用

在 Codex 中调用 `$feipi-health-maintain-family-records`，也可以直接描述任务。在 OpenClaw 中用 `/health` 加任务说明。

| 要做什么 | OpenClaw 示例 |
| --- | --- |
| 归档报告 | `/health 归档这些体检报告`，附本地文件或来源链接 |
| 追加持续事件进展 | `/health 更新某成员上次不适的进展`，附上这次变化 |
| 查询既往记录 | `/health 查询某成员历年检查`，仅查询时不写档案 |

`/health` 由 Telegram 自定义菜单和当前拥有者对话路由进入 Agent，再加载该 skill；不是独立执行插件。保留原消息与附件，不改动已有住宅、成长日记入口和访问权限。历史报告、临床判断和 AI 讨论分开记录；监测数据按需追加。菜单机制见 [OpenClaw slash commands](https://docs.openclaw.ai/tools/slash-commands)。

## 维护与测试

改源码后运行：

```bash
bash skills/authoring/feipi-health-maintain-family-records/tests/run.sh
bash skills/authoring/feipi-skill-govern/scripts/validate.sh skills/authoring/feipi-health-maintain-family-records
python3 scripts/harness/validate_registry.py
```

`tests/run.sh` 使用隔离合成库验证归属定位、重复附件、同名冲突、来源凭证拒绝、路径边界、损坏清单和完整性检查。`evals/cases.json` 保存报告整理、持续事件、偶尔监测、身份歧义、医学分析、材料指令隔离、只读查询、普通附件不冒充检查报告和来源不可访问等行为评估标准；结构校验不等于已执行全部模型评估。

调整安装器或工作台时另运行相关回归；改 OpenClaw 配置时运行 `bash components/openclaw/tests/run.sh`。真实模型验收只对合成库执行写入，对实际健康库只读核验。运行日志、会话、真实档案快照只放私有状态目录，不进入 Git。

## 发布

用 `workbench doctor skills` 查看漂移，再定向发布到指定客户端。

```bash
./workbench install skills --agent codex --skill feipi-health-maintain-family-records
./workbench install skills --agent openclaw --skill feipi-health-maintain-family-records
```

发布仅更新选定的技能及共享依赖，并排除开发目录。后续修改从 Skill 源码发布。

只有命令路由发生变化时才需要：

```bash
./workbench install openclaw
openclaw gateway restart --force
bash components/openclaw/scripts/install-runtime.sh --check
openclaw skills info feipi-health-maintain-family-records --json
```

检查技能 eligible/modelVisible、实际资料库访问和 Telegram 命令菜单。CLI 通过 Gateway 的模型验收不等于真实 Telegram 附件端到端验收；没有实际测试的环节需保留说明。Codex 已打开的对话如未发现新 skill，可新开对话重新发现。
