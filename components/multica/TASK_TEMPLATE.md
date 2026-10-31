# 任务标题

目标：

范围：仓库/资料位置，允许修改的内容。

输入：来源链接、文件、必要上下文。

验收：可检查的结果、测试或核对方法。

交付：提交/PR、可下载文件、补丁或其他可恢复成果。

依赖：前置任务、权限和待用户决定的事项。

来源标识：外部请求的稳定标识；重试时先检查是否已录入。

执行方式：仅记录 / Codex Builder / OpenClaw Assistant。未明确执行时保持未分派。

交付先进入 Review，由用户验收。不能只记录会被回收的临时工作目录。

## 跨工具交接包 handoff.json

```json
{
  "objective": "具体结果",
  "scope": "允许修改范围和项目规则位置",
  "directory": "/实际项目目录",
  "acceptance": "验证步骤和标准",
  "artifacts": ["已有提交、附件或文件"],
  "remaining": ["剩余工作、失败层和接手建议"],
  "required_commands": ["git"],
  "required_mcp": []
}
```

只有明确要求后台执行时调用 multica-work dispatch；执行者用逻辑键绑定准确 runtime。model、OpenClaw Agent ID、LiteLLM 路由分别记录。桌面 MCP 未实际在后台验证时不得列为可用能力。进度用 note；需要下一角色运行时用 handoff。
