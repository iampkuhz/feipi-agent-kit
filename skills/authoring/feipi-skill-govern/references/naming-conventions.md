# Skill 命名规范（强制版）

## 目标

统一个人技能库命名，避免与外部技能重名，并且一眼看出技能用途。

## 强制格式

所有 skill 名称必须满足：

```txt
feipi-<action>-<target...>
```

约束：
- 前缀固定：`feipi-`
- 至少 3 段（`feipi` + `action` + `target`）
- 仅允许：小写字母、数字、连字符
- 总长度 <= 64
- 与目录名一致
- 禁止保留词：`anthropic`、`claude`

正则参考：
- 基础：`^[a-z0-9-]{1,64}$`
- 结构：`^feipi-[a-z0-9]+-[a-z0-9-]+$`

## action 标准字典（第二段固定）

仅允许以下 action：
- `coding`：生成/修改代码
- `gen`：通用内容生成（文档、模板、配置）
- `read`：读取/提取信息（含视频、音频、文档）
- `write`：写入/改写
- `analyze`：分析与归纳
- `review`：审查与评估
- `test`：测试相关
- `debug`：故障排查
- `refactor`：重构
- `docs`：文档工程
- `data`：数据处理
- `git`：版本控制工作流
- `web`：前端与页面
- `ops`：运维与发布
- `build`：构建相关
- `deploy`：部署相关
- `migrate`：迁移相关
- `automate`：自动化流程
- `monitor`：监控巡检
- `summarize`：摘要汇总
- `translate`：翻译本地化
- `design`：方案设计
- `planning`：计划拆解
- `govern`：技能治理与规范化
- `skill`：skill 工程与治理（仅用于 `feipi-skill-govern`）

## target 规范（第三段及以后）

- 使用对象/载体/场景词，尽量具体。
- 推荐 1~3 段，避免过长。

示例 target：
- `react-components`
- `api-tests`
- `video-transcript`
- `pdf-forms`
- `pr-comments`

## 你关心的常见命名示例

1. 生成代码：
- `feipi-coding-react-components`
- `feipi-coding-api-clients`
- `feipi-gen-code-snippets`（偏模板化生成）

2. 读取视频：
- `feipi-read-video-transcript`
- `feipi-read-video-keyframes`
- `feipi-read-video-summary`

3. 测试与调试：
- `feipi-test-api-contracts`
- `feipi-debug-build-failures`

4. 文档与评审：
- `feipi-docs-architecture-notes`
- `feipi-review-pull-requests`

## 禁止命名

- `helper`、`utils`、`tools`、`misc`
- `my-skill`、`temp`、`tmp-fix`
- 带时间版本：`report-2026-q1`、`skill-v2`

## 冲突处理

1. 如果与现有 skill 语义重叠，优先扩展原 skill，不新建重复项。
2. 若确需拆分，使用更具体 target 区分：
- `feipi-coding-react-components`
- `feipi-coding-react-hooks`

## 新建前检查清单

```txt
命名检查
- [ ] 以 feipi- 开头
- [ ] 格式为 feipi-<action>-<target...>
- [ ] action 在标准字典中
- [ ] 名称总长 <= 64
- [ ] 不含 anthropic/claude
- [ ] 与现有技能不重复
```
