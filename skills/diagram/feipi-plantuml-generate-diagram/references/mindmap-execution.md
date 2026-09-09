# Mindmap 执行合同

## 输入与调用

正常单图只需填写 `assets/templates/types/mindmap-brief.yaml` 并调用：

```bash
python3 scripts/run_mindmap.py --brief brief.yaml --out-dir package
```

脚本按自身位置定位 schema、样式与内部工具，brief/out-dir 相对调用者的工作目录；路径含空格或中文时按 shell 规则引用。默认向右，用户明确要求时由 brief 选择其他方向。

`diagram_id` 沿用单图 `D1` 最简；自定义允许 `technical-review` 这样的 slug，不允许下划线。`nodes.id` 与 parent 引用允许下划线。这两种 ID 不显示在图上。

默认沿用 `AGENT_PLANTUML_SERVER_PORT`（缺省 8199）。已有服务使用不同基础地址时，可以增加唯一的地址覆盖参数 `--server-url <loopback-url>`，地址直接交给原 preflight，成功后只使用它返回的 `renderer_url`。不传 schema 路径、不手动推导产物路径。批次多图继续使用主入口的共享 preflight 流程。

## 依赖与平台

- 支持现有 POSIX 运行环境：macOS、Linux，以及具备相同依赖的 WSL；不宣称支持原生 Windows shell。
- 运行依赖：Python 3.10+、Bash、curl，以及 PyYAML 或 Ruby（沿用既有 YAML 加载方式）。它们必须在调用环境中可用。
- PNG 预览固定使用 librsvg 的 `rsvg-convert`，不使用 macOS 专属 `qlmanage`，也不由模型尝试多种转换器。缺少该依赖时在 renderer 调用前返回 `missing_dependencies`，不自动安装。
- 默认地址的服务尚未运行时，仍只有原 preflight 的一次固定 Podman 启动例外；Podman 不是已有 renderer 场景的强制依赖。自定义端口/地址不可用时不会启动默认端口容器。
- 中文显示依赖 renderer 和本地预览环境的字体；实际查看 PNG 后判断。缺字不等于源码语法错误，不自动修改服务或字体配置。

## 返回与产物

stdout 只返回一份 JSON，退出码 0 表示执行及预览完成，1 表示 blocked：

```json
{"status":"success","stage":"complete","reason":"","issues":[],"visual_review":"pending","paths":{"diagram":"绝对路径/diagram.puml","svg":"绝对路径/diagram.svg","preview":"绝对路径/diagram.png","validation":"绝对路径/validation.json"}}
```

`paths` 还可包含 brief、preflight、log；只列已经存在的文件。子命令完整输出写入 `run.log`；工作目录准备成功后，`run-result.json` 保存同一份摘要。准备或依赖失败时可能只有 stdout 回执。

`stage` 为 prepare/dependencies/brief/preflight/generate/validate/preview/complete；优先看 `reason` 与至多三条 issues，必要时读取对应日志或回执。摘要不代替既有 v1.2 `validation.json`，前置失败不伪造图包成功合同。

`visual_review: pending` 只表示预览已准备，尚未看图。查看 `paths.preview` 后确认中文可读、层级/方向正确、无截断，再交付 SVG 与源码。SVG 图包通过但 PNG 转换失败时，总入口仍返回 blocked/preview，并保留已验证的 SVG。

## 重复执行与边界

- 本入口只处理首次生成；目录可预先包含输入 brief，但不得已有 PUML、SVG、PNG、图包合同或 preflight 回执。
- 已有图包或失败预检产物返回 `existing_package`，不覆盖用户源码、不重新预检，也不重置计数。修复/复用走原 `validate_package.sh` 与 `--reuse-valid-package` 合同；不能通过换目录反复渲染同一失败图。
- 入口不增加网络重试、健康检查或服务管理。前置 brief 失败的 renderer 请求为 0；预检成功后只调用一次图包验证，按既有图包合同处理失败。
- 子进程在本次程序调用中顺序等待完成；内部预检、网络和预览均有明确边界。外层工具若提前 yield，应继续等待同一个进程，不重新启动入口。固定的是业务执行路径，不承诺不同客户端的外层等待往返数相同。

## 验证入口

- `scripts/tests/test_mindmap_runner.py`：隔离 fixture 测试路径、配置、依赖、失败与结果格式；不作为真实渲染证明。
- `scripts/test.sh`：用真实 renderer 执行 mindmap 统一入口，并将该回执共享给批次其他图型；真实 SVG 与 PNG 必须存在。
