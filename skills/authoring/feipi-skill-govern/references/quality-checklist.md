# 技能质量清单（精简版）

使用方式：复制并打勾；每一项需对照对应参考文件核对。

```txt
技能质量清单
- [ ] 已锁定目标 skill 与允许改动的直接共享文件
- [ ] 已对照 `references/repo-constraints.md` 完成硬约束核查
- [ ] `description`、`short_description`、`default_prompt`、`SKILL.md` 对“做什么 / 什么时候用 / 什么时候别用”的表述一致
- [ ] `SKILL.md` 已写清输入、输出、默认策略、失败处理与验证方式
- [ ] 模板、共享脚本与 skill 文档未冲突，且无残留占位符
- [ ] 过程与验证符合 `references/workflow.md`
- [ ] 变更记录与 README 同步符合 `references/changelog-policy.md`
- [ ] 已确认目标 skill 的 `agents/openai.yaml` `version` 符合当日规则（首次修改升版，同日后续修改不重复升版）
- [ ] `CHANGELOG.md` 已在对应日期下按该 skill 的新版本写清合并后的更新内容
- [ ] 已运行 `bash scripts/validate.sh <skill-dir>`
- [ ] 已完成至少一种任务级验证；若改了模板或初始化脚本，已生成临时 skill 验证
- [ ] 已记录验证结果与剩余风险
```
