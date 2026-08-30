# 通用渲染规则

## Server 发现

- 优先使用 `AGENT_PLANTUML_SERVER_PORT` 环境变量指定的本地端口。
- 默认端口 `8199`。
- 默认只使用 `http://127.0.0.1:<port>/plantuml`；显式地址也必须是 loopback。
- 默认消费已存在的 renderer。唯一启动例外是批次 preflight 首次不可用时执行一次固定 Podman 命令；禁止杀死、重启、长时间等待或排查 PlantUML renderer/proxy。

## 批次预检

1. 每个批次在创建任何图 worker 前只运行一次 `scripts/preflight_renderer.sh`。
2. 每次探测连接超时不超过 1 秒、请求总超时不超过 2 秒，只渲染固定最小探针图。
3. 首次不可用且目标是默认 8199 端口时，只执行一次 `podman run --rm -d -p 8199:8080 --name plantuml docker.io/plantuml/plantuml-server:jetty`；命令默认最多等待 30 秒，成功后等待 1 秒，再复检一次。
4. 成功时冻结唯一 `renderer_url`，后续所有图显式复用该地址，不再自动发现。
5. 复检仍失败时返回 `blocked_reason=render_server_unavailable`；不再重试、不切换地址、不创建 worker，也不停止或排查容器。

## 渲染流程

1. 将 `.puml` 源码 URL-encode。
2. 请求 preflight 冻结地址的 `/plantuml/svg/<encoded>` 端点；成功路径只请求 SVG，不再先请求 `/txt`。
3. 从 HTTP 状态、SVG 根元素和错误 SVG 中识别成功、语法错误或 server 不可用。
4. 仅在显式使用 `--reuse-valid-package` 且现有图包通过当前路径、hash、metrics、profile 与 `render_contract_version` 复核时复用，不访问 renderer。
5. 新生成的 `validation.json.timings` 分别记录总耗时、SVG 请求耗时和除 SVG 请求外的静态校验耗时；命中复用时保留原图包，不把历史 render timing 记作本次请求。

## 渲染失败处理

- HTTP 非 200 或地址不可达：只由批次 preflight 执行上述一次启动和一次复检；仍失败则标记 `final_status=blocked`、`blocked_reason=render_server_unavailable`。
- renderer 脚本或 renderer 身份缺失、当前运行未生成或未命中受约束复用的 SVG 时一律阻塞；未通过复用检查的旧 SVG 必须在渲染前失效。
- PlantUML 返回语法错误：标记 `render_result=syntax_error`。
- 渲染成功但 SVG 为空或过小：标记 `render_result=skipped`。

## 注意事项

- 自循环修复期间只读取 `validation.json` 和修改失败 `.puml`，不要重新读取规则文件。
- brief/profile/rules hash 未变化时复用冻结 brief 校验；`.puml` 变化后仍需重跑 coverage/layout。
- 每张图总渲染上限为 2 次：首次生成 1 次、针对性修复 1 次。
- 纯视觉审美问题交给 reviewer，不自动回流渲染。
