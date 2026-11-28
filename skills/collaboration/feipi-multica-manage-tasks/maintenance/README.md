# 维护入口

- `SKILL.md` 负责选择任务协作入口，`references/` 维护官方 CLI 的操作约定。
- `scripts/project.py` 负责项目定位、只读查询及仓库协作入口。显式项目依赖 CLI 登录态，目录自动发现使用私有 Cloud 绑定。
- `tests/run.sh` 运行项目和组件确定性回归。Cloud 端到端验收使用已授权的测试项目，验证实际评论、Run 和附件。
