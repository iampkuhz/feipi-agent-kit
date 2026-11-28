# Frontmatter 规范

## 字段要求

- 仅保留 `name` 与 `description` 两个字段。
- `name` 与目录名一致。
- `description` 非空，使用第三人称，<= 1024 字符。
- `description` 建议同时覆盖“做什么”和“什么时候用”，通常控制在 30 到 100 字内。
- Frontmatter 不包含 XML 标签。

## 示例

```markdown
---
name: skill-name
description: 用第三人称描述 skill 的核心能力与触发时机（建议 <=100 字）
---
```

## 常见错误

| 错误 | 修复 |
|------|------|
| 缺少 name 字段 | 添加与目录名一致的 name |
| description 为空 | 补充第三人称描述 |
| description 过长 | 精简到合理长度，硬上限 1024，建议 100 字以内 |
| 包含 XML 标签 | 移除标签 |
