# 技能质量清单（精简版）

使用方式：复制并打勾；每一项需对照对应参考文件核对。

```txt
技能质量清单
- [ ] 已对照 `references/repo-constraints.md` 完成硬约束核查
- [ ] 命名符合 `references/naming-conventions.md`
- [ ] 环境变量符合 `references/env-policy.md`
- [ ] 过程与验证符合 `references/workflow.md`
- [ ] 变更记录与 README 同步符合 `references/changelog-policy.md`
- [ ] 已递增目标 skill 的 `agents/openai.yaml` `version`
- [ ] `CHANGELOG.md` 已在对应日期下按该 skill 的新版本写清合并后的更新内容
- [ ] 已运行 `make validate DIR=<skill-root>/<name>`
- [ ] 已完成至少一种任务级验证并记录结果
```
