# 本地渲染与依赖

需要 Python 3.10+（PyYAML 6、jsonschema 4）、Node.js 22.13+、Chrome/Chromium。运行只使用固定 lockfile 中的 Mermaid CLI 12.0.0、Mermaid、Puppeteer；浏览器进程仅为本次调用创建并在结束时关闭。没有服务端口、容器或在线渲染服务。

在 skill 目录准备依赖：

```bash
python3 -m pip install -r scripts/requirements.txt
PUPPETEER_SKIP_DOWNLOAD=true npm ci --ignore-scripts --no-audit --no-fund
node scripts/render.mjs --check
```

优先使用已安装的 Google Chrome（macOS）或 /usr/bin 下的 Chromium/Chrome。其他位置在 run.py 和 render.mjs 传 `--browser /absolute/path/to/chrome`。没有浏览器时明确报告缺少依赖，让用户安装其选择的浏览器，不暗中切换公共 renderer。

预检只启动一次短生命周期浏览器以确认可用性，不渲染用户图。正式渲染单独启动浏览器，65秒上限；超时只终止本次调用创建的进程组。没有 `--no-sandbox`、自动提权或反复重启。连接权限错误与依赖不存在是不同失败层。

渲染依赖的伪域名 `mermaid-cli-intercept.invalid` 由 CLI 本地拦截并从依赖目录加载资源；其他 HTTP 请求全部拒绝。图包仍应避免包含密钥等不需要展示的输入。PNG 使用白底与系统中文字体，SVG 不嵌入字体，跨机显示可能因字体不同而变化；以同时交付的 PNG 核对视觉。

官方依据（2026-10-29 核对）：[CLI](https://github.com/mermaid-js/mermaid-cli)、[flowchart](https://mermaid.js.org/syntax/flowchart.html)、[sequence](https://mermaid.js.org/syntax/sequenceDiagram.html)、[mindmap](https://mermaid.js.org/syntax/mindmap.html)。依赖升级要重新验收样例和几何选择器，不能只更新版本号。
