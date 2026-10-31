# 适配清单与责任边界

2026-10-31，机器身份在私有 machine.json 中；这里只记录逻辑职责。具体实测见 VALIDATION.md。

| 适配 | 当前落地 | 检查/维护入口 |
|---|---|---|
| Codex Builder | 原生 App Server；model=gpt-6.1-sol/high；保留 LexiFlow 的局部工作包约束 | Agent 声明、精确 Codex runtime、共享 Skill |
| Qoder Worker | 原生 ACP；CLI 账户默认模型；并发 1；不加入 LexiFlow 正式链 | 新建并绑定准确 Qoder runtime，实际任务取证 |
| LiteLLM Coder | 隔离 OpenClaw local；selector=litellm-coder；路由 litellm/litellm-code-openai | provider 配置继续由原 OpenClaw 声明和 LiteLLM catalog 生成 |
| OpenClaw Assistant | 同一隔离 runtime 的 main selector；保留已有默认模型 | 单独 Agent UUID，不与个人 runtime 混选 |
| Coordinator/Validator/Reviewer | 保留原项目职责与模型、验收权限 | 项目原流程维护；新层只做身份和协作配置 |
| 个人 OpenClaw | 作为录入、查询和显式交接入口；原渠道/记忆不复制到后台 | Agent Kit 安装共享 Skill；不重启个人 Gateway |
| 原个人 OpenClaw runtime | 不在本配置的执行绑定内 | 不能仅按 provider 选中；plan 核对 UUID/daemon/profile |
| 技能 | 说明、脚本、引用文件、依赖文件完整核对；源码与安装目标比较 | 既有安装器 + doctor 内容摘要；workspace Skill 显式附加 |
| MCP | 保留 provider 原生继承语义；隔离 OpenClaw 发现与执行来源一致 | 必需/可选能力声明；无任务内证据则不声称可用 |
| 项目绑定 | LexiFlow、ASD 的已管理本地 resource UUID；其他资源保留 | 新机器先生成目录与 daemon，再 plan/apply |
| 进度/派发 | note 静默；dispatch 静默归属+一次正常 @评论；handoff 正常 @交接 | request-id 本机回执、原生 trigger_outcomes/runs 读回 |
| 认证 | personal 供日常；完整任务契约供后台；缺项拒绝 | multica-task，独立缺项测试与实机评论归属 |
| 恢复/迁移 | 排空、同批备份、校验清单、重新认证与重绑 | backup、Mac mini 手册；不复制 daemon 设备身份 |

## 尚需按场景扩展的能力

- 必需 MCP 的真实后台调用：本轮没有把桌面工具等同后台工具；通用 dispatch 遇到非空 required_mcp 会拒绝，需要为具体 MCP 增加真实任务探针再开放该要求。
- 视频技能已在 Codex/Qoder/个人 OpenClaw 一致安装；隔离 OpenClaw 没有自动继承所有个人技能。需要视频后台任务时，先绑定完整视频技能及依赖，再做提取验收，不能仅凭本轮编码验收声明可用。
- 当前任务入口约束为单主力机器的 in_place 项目；原生 worktree 仍可使用原有项目流程。跨机器和直接 UI 同时派发不是本机回执锁能提供的分布式事务。
- Mac mini 真机冷启动、后台 Documents 权限、私网接入和全量恢复需到货后执行。MacBook 的 record/note 可连接新服务；需要检查新机目录并派发时，在 Mac mini 上运行 multica-work（可经既有 SSH），不拿 MacBook 的本地目录检查代替远端检查。
