# 通用渲染规则

## Server 发现

- 优先使用 `AGENT_PLANTUML_SERVER_PORT` 环境变量指定的本地端口。
- 默认端口 `8199`。
- 默认只使用 `http://127.0.0.1:<port>`；显式地址也必须是 loopback。
- 默认消费已存在的 renderer。唯一启动例外是批次 preflight 首次不可用时执行一次固定 Podman 命令；禁止杀死、重启、长时间等待或排查 PlantUML renderer/proxy。

## 批次预检

1. 每个批次在创建任何图 worker 前只运行一次 `scripts/preflight_renderer.sh`。
2. 每次探测连接超时不超过 1 秒、请求总超时不超过 2 秒，只渲染固定最小探针图。
3. 首次探测若识别到明确连接权限错误，立即返回 `blocked_reason=render_access_denied`，不启动 Podman、不复检。其他不可用且目标是默认 8199 端口时，只执行一次 `podman run --rm -d -p 8199:8080 --name plantuml docker.io/plantuml/plantuml-server:jetty`；命令默认最多等待 30 秒，成功后等待 1 秒，再复检一次。
4. 成功时冻结唯一 `renderer_url`，后续所有图显式复用该地址，不再自动发现。
5. 复检若遇到明确连接权限错误，同样返回 `render_access_denied`；其他失败返回 `render_server_unavailable`。不再重试、不切换地址、不创建 worker，也不停止或排查容器。

预检回执的 `podman_start_result` 表示本次启动决策：`renderer_available` 表示首次探测已取得有效 SVG、renderer 可用且未执行 Podman 启动；`started` 表示已成功执行一次固定 Podman 启动；`failed` / `timeout` 表示启动命令未成功；`podman_unavailable` 表示需要启动但找不到 Podman；`skipped_access_denied` 表示连接访问被拒绝而未尝试启动。该字段不用于推断 renderer 由哪个进程或容器提供。

## 渲染流程

1. 将 `.puml` 源码 URL-encode。
2. 在 preflight 冻结的基础地址后追加 `/svg/<encoded>`；成功路径只请求 SVG，不再先请求 `/txt`。
3. 从 HTTP 状态、SVG 根元素和错误 SVG 中识别成功、语法错误或 server 不可用。
4. 仅在显式使用 `--reuse-valid-package` 且现有图包通过当前路径、hash、metrics、profile 与 `render_contract_version` 复核时复用，不访问 renderer。
5. 新生成的 `validation.json.timings` 分别记录总耗时、SVG 请求耗时和除 SVG 请求外的静态校验耗时；命中复用时保留原图包，不把历史 render timing 记作本次请求。

## 渲染失败处理

- 明确连接权限错误：curl 退出码为 7，且英文诊断包含 `Operation not permitted` 或 `Permission denied`，才分类为 `permission_denied`。`check_render.sh` 与 preflight 返回码为 5；预检与图包均记录 `blocked_reason=render_access_denied`。仅凭 curl 7、超时或无响应不能确认权限限制；本地文件读写权限错误也不归入连接权限错误。
- 权限失败的低层输出保留目标地址、curl 退出码、HTTP 状态与原始错误；预检回执对应 `render_target/curl_exit_code/http_status/issue`，并增加 `failure_kind=permission_denied`。图包 `issues` 保留这些诊断，`failure_class=renderer`、`repairable=false`。HTTP `000` 表示未取得 HTTP 响应。
- 报告访问被拒绝时，沙箱只是可能原因，需宿主证据才能确认。脚本不提权、不修改权限；宿主不允许审批时停止。没有明确权限错误的连接失败仍按不可用处理，但不能声称已证明服务宕机。
- 其他 HTTP 异常或地址不可达：只由批次 preflight 执行上述一次启动和一次复检；仍失败则标记 `final_status=blocked`、`blocked_reason=render_server_unavailable`。
- renderer 脚本或 renderer 身份缺失、当前运行未生成或未命中受约束复用的 SVG 时一律阻塞；未通过复用检查的旧 SVG 必须在渲染前失效。
- PlantUML 返回语法错误：标记 `render_result=syntax_error`。
- 渲染成功但 SVG 为空或过小：标记 `render_result=skipped`。

## 注意事项

- 普通图面修复只读取 `validation.json` 和修改失败 `.puml`；静态与 renderer 冲突时退出该循环，按目标 skill 维护授权读取直接相关规则与实现。
- brief/profile/rules hash 未变化时复用冻结 brief 校验；`.puml` 变化后仍需重跑 coverage/layout。
- 每张图总渲染上限为 2 次：首次生成 1 次、针对性修复 1 次。
- 纯视觉审美问题交给 reviewer，不自动回流渲染。
- 上限按同批次同图累计，不按输出目录分别计算。语法错误不能通过重启 renderer 或重复权限授权解决。
- 静态规则与 renderer 冲突时转入用户授权的目标 skill 维护，保留失败记录；修复合同后记录独立验证批次，不将其冒充原失败图的缓存命中。
- 正向集成测试必须断言真实渲染成功；允许 `success` 或 `blocked` 二选一会掩盖不可渲染样例，不得作为正向通过条件。
