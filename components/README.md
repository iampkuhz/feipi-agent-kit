# 受管组件源码

日常入口是根目录 `./workbench`，研发入口是 `./develop`。这里复用已有组件实现，不另建 Git 仓库、不使用子模块、不把 HOME 私有状态复制进来。

| 目录 | 本次引入来源 HEAD | 保留方式 |
| --- | --- | --- |
| mac | dotfiles `71cf9f683b70a08092ceed2114dc4926e0f43e09` | 带入原未提交 bootstrap/Zsh 改进；运行副本与研发目录分开 |
| multica | multica-ops `b2c71500a8d7749b83ffb0588867b44378773911` | 带入原适配/任务工作；继续复用 ops 发布及数据库备份 |
| openclaw | 新 feipi-openclaw `735a1861b0cc6aa2b3b47c4cac3a10fb67b3818d` | 带入原微信/成长日记等工作；保留原状态与版本锁定 |
| openclash | 路由器实际活动模块 | 只收无凭据模块及操作脚本；最小配置备份在私有 HOME |

旧 OpenClaw `2b2c99ebb41355c405dcee404ea6dab54dd46aef` 为新来源祖先，落后 9 commits，未作为第二个独立数据源导入。各原仓库与其 Git 历史仍在原位置；统一工作台的新改动只在当前 feipi-agent-kit 记录。首次工作区归档、patch/status 与源文件摘要保存在本机私有备份，详见 [来源记录](../docs/workbench-plan.md)。

源码回归通过后显式 `workbench apply` 才进入日常环境。组件内部部署命令是维护接口，使用前读各自 AGENTS.md；不要重新建立日常环境到旧源码目录的链接。
