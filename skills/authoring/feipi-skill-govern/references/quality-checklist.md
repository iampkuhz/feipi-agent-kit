# 技能质量清单

使用方式：复制并逐项核对；未打勾项不能视为完成。

```txt
治理前置
- [ ] 已锁定唯一 target_skill
- [ ] 已锁定 allowed_shared_files
- [ ] 已判断本次任务属于 create / refactor / govern / self-audit 之一

命名与 layer
- [ ] 已按 domain -> action -> object -> layer 决策
- [ ] target_name 符合 feipi-<domain>-<action>-<object...>，或明确属于 feipi-skill-govern 特例
- [ ] target_layer 只用于目录，不混入 skill 主语法
- [ ] 未把 web/ops/automate 当默认 action

触发层
- [ ] description、short_description、default_prompt 已同时写清“做什么 / 什么时候用 / 什么时候别用”
- [ ] 已明确它是治理型 skill 还是普通业务 skill，避免误触发

执行层
- [ ] SKILL.md 已写清输入、输出、默认策略、失败处理与验证方式
- [ ] 已写清只改目标 skill 与直接共享文件的边界
- [ ] 已写清主入口与包装器关系

资源与脚本
- [ ] references/ 只保留需要下沉的长规则、案例、清单
- [ ] scripts/ 只保留确定性、可复用、可验证脚本
- [ ] assets/ 只保留真正复用的模板或静态资源
- [ ] 核心流程可通过当前 skill 本地脚本闭环，不依赖仓库级共享脚本

验证
- [ ] 已运行结构校验主入口
- [ ] 已完成至少一种行为校验
- [ ] 若改了模板或初始化逻辑，已生成临时 skill 验证
- [ ] 已完成旧规则残留搜索
- [ ] 已区分仓库根命令与 skill 本地命令

收口
- [ ] 已记录 current_name、target_name、target_layer、rename_reason、migration_risk
- [ ] 已记录 script_localization_status 与 validation_status
- [ ] 已按 version-policy 与 changelog-policy 收口
- [ ] 已把其他 skill 的问题写入待重审清单，而不是顺手扩散修改
```
