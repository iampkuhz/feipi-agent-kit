# 通用渲染规则

## Server 发现

- 优先使用 `AGENT_PLANTUML_SERVER_PORT` 环境变量指定的本地端口。
- 默认端口 `8199`。
- server 候选地址见 `assets/server_candidates.txt`。

## 渲染流程

1. 将 `.puml` 源码 URL-encode。
2. 依次尝试各 server 候选地址的 `/plantuml/svg/<encoded>` 端点；成功路径只请求 SVG，不再先请求 `/txt`。
3. 从 HTTP 状态、SVG 根元素和错误 SVG 中识别成功、语法错误或 server 不可用。
4. 仅在显式使用 `--reuse-valid-package` 且现有图包通过当前路径、hash、metrics、profile 与 `render_contract_version` 复核时复用，不访问 renderer。
5. 新生成的 `validation.json.timings` 分别记录总耗时、SVG 请求耗时和除 SVG 请求外的静态校验耗时；命中复用时保留原图包，不把历史 render timing 记作本次请求。

## 渲染失败处理

- HTTP 非 200：尝试下一个候选 server。
- 全部候选 server 不可达：标记 `render_result=skipped`、`final_status=blocked`、`blocked_reason=render_server_unavailable`。
- renderer 脚本或 renderer 身份缺失、当前运行未生成或未命中受约束复用的 SVG 时一律阻塞；未通过复用检查的旧 SVG 必须在渲染前失效。
- PlantUML 返回语法错误：标记 `render_result=syntax_error`。
- 渲染成功但 SVG 为空或过小：标记 `render_result=skipped`。

## 注意事项

- 自循环修复期间不要重新读取规则文件。
- 循环期间只读取 `validation.json` 和修改 `.puml`。
- 每张发生变化的图默认最多修复并重渲染 2 轮；只重跑失败或内容变化的图。
