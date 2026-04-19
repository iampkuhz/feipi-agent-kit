# 语言与输出规范

> **适用场景**：所有面向用户的可见输出
> **优先级**：high

---

## 1. 默认输出语言

所有面向用户的可见输出默认使用**简体中文**。

这包括但不限于：
- 分析、拆解、计划、步骤说明
- 审阅意见、总结、修改说明
- 错误解释、调试过程描述
- 文档、注释、README
- 若底层模型暴露 reasoning / planning summary 等可见过程文本，也必须使用简体中文表达

## 2. 保留英文原文的内容

以下内容**不翻译**，保持英文原样：

| 类别 | 示例 |
|------|------|
| 代码 | `def foo():`, `class Bar` |
| Shell 命令 | `podman run`, `git status` |
| 文件路径 | `/etc/nginx/conf.d/` |
| JSON / YAML key | `"api_key"`, `timeout: 30` |
| API / class / function / library / protocol 名称 | `HTTP`, `PostgreSQL`, `FastMCP`, `OTLP` |
| 必要的行业术语原文 | `OAuth`, `WebSocket`, `MCP` |

## 3. 英文中间信息处理

如果底层模型、工具调用或外部系统返回英文中间结果：

- **不要**大段原样抛给用户
- 应优先给出**中文解释、中文归纳或中文结论**
- 仅在必要时保留英文原文片段作为引用，并附中文说明

示例：

```
错误做法：
The connection was refused because the service is not listening on port 8080.

正确做法：
连接被拒绝：服务未在 8080 端口监听（原文："The connection was refused..."）
```

## 4. 术语风格

采用"中文说明 + 英文术语原文"风格，避免生硬全翻译：

```
正确：调用 LiteLLM 网关的 /v1/chat/completions 接口
生硬：调用轻大语言模型网关的虚拟一聊天完成接口

正确：在 PostgreSQL 中创建 B-tree 索引
生硬：在 постгрес 中创建 B 树索引
```

## 5. 禁止项

- 不要声称可以控制不可见的 hidden thinking 语言
- 不要伪造不存在的配置项（如 `thinkingLanguage`）
- 不要承诺"100% 消除英文"——本规则仅约束 agent 的可见输出行为

## 6. 风格约束

- **结论先行**：先给结果，再给过程
- **条理输出**：分点说明，避免大段文字
- **少废话**：不做多余的铺垫和总结
- **中英不混排**：中文句子中嵌入英文术语时保持自然，避免逐字切换

---

## 参考

- `AGENTS.md` — 仓库级 agent 指南（强约束第1条）
- `rules/README.md` — rules 目录说明
