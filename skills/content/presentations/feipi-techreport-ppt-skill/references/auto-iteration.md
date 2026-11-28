# 有效迭代

本文件保留旧名称以兼容引用，但当前系统不对同一 IR 执行“最多三轮”的无效重复。

一次有效迭代必须满足：

1. 前一轮返回明确 issue、overflow action 或用户决策；
2. 对 Composition、IR、Component/Layout Contract 或 token 做了有依据的变更；
3. 新输入 hash 与前一轮不同；
4. 重新执行完整校验，而不是只跳过失败门禁；
5. 报告变更原因和仍未解决的问题。

若 IR hash 未变化，Pipeline 立即停止并返回原有结构化状态。它不会生成 repair plan 后继续检查同一份 IR，也不会通过自动缩小字号制造“修复”。

只有 `compress_text`、`change_component_size` 和不改变业务含义的 `change_layout` 可以由 agent 在既有授权范围内执行。`drop_secondary` 涉及重要内容、`split_required` 或业务含义变化时请求用户。
