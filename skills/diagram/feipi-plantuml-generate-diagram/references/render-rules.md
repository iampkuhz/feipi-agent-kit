# 通用渲染规则

## Server 发现

- 优先使用 `AGENT_PLANTUML_SERVER_PORT` 环境变量指定的本地端口。
- 默认端口 `8199`。
- server 候选地址见 `assets/server_candidates.txt`。

## 渲染流程

1. 将 `.puml` 源码 URL-encode。
2. 依次尝试各 server 候选地址的 `/plantuml/svg/<encoded>` 端点。
3. 返回 SVG 内容或标记为 server 不可用。

## 渲染失败处理

- HTTP 非 200：尝试下一个候选 server。
- 全部候选 server 不可达：标记 `render_result=skipped`、`final_status=blocked`、`blocked_reason=render_server_unavailable`。
- renderer 脚本或 renderer 身份缺失、当前运行未生成 SVG 时一律阻塞；开始验证前必须让旧 SVG 失效。
- PlantUML 返回语法错误：标记 `render_result=syntax_error`。
- 渲染成功但 SVG 为空或过小：标记 `render_result=skipped`。

## 注意事项

- 自循环修复期间不要重新读取规则文件。
- 循环期间只读取 `validation.json` 和修改 `.puml`。
- 最大重试次数 5 次。
