# Multica 运维约定

- 本目录只维护部署定义、无秘密模板、操作脚本和验收记录。
- 服务使用固定版上游 checkout；真实 env、CLI token、数据库与附件不进入本目录。
- 全局秘密源为 `~/.env` 所指向的本机 env vault；只投影 Multica 所需变量，不加载整个全局环境给任务。
- 不输出 token、密码、验证码或展开后的 Compose environment。
- 服务、daemon 和 OpenClaw Gateway 分别操作，不能重启无关容器。
- 迁移/升级前排空任务，数据库和附件保存同一批次；不复制两机共用的 runtime 身份。
- 本机试点并发为 1；任务完成必须核实交付物、验证结果与 Issue 状态。
