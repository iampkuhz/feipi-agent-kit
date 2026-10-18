# OpenTelemetry Collector — Claude Code 本地调试

最小化 OTel Collector，用于接收并落盘 Claude Code 发出的 OTel logs，方便本地 grep / jq 分析。

不采集 metrics，不采集 traces。

## 架构

```
Claude Code ──(gRPC)──▶ OTel Collector ──▶ claude-code-otel.raw  (原始 OTLP JSON)
                                    │
                                    └──▶ cleaner (python) ──▶ claude-code-otel.jsonl  (干净 JSONL)
```

## 启动

以下命令在仓库根执行；本机环境见 [新 Mac 重建](../../../docs/setup-new-mac.md)。

```bash
make otel-up
make otel-status
```

## 停止

```bash
make otel-down
```

## Claude Code 环境变量

在 Claude Code 启动前设置：

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_LOGS_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=none
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317
export OTEL_LOGS_EXPORT_INTERVAL=1000
```

## 落盘文件

默认路径：`$HOME/Documents/service-data/otel/`，跟随当前用户；可用 `AGENT_SERVICE_DATA_DIR` 改数据根目录。启动脚本自动创建目录，状态检查不创建。

| 文件 | 说明 |
|---|---|
| `claude-code-otel.jsonl` | **干净 JSONL**，每行一条，可直接 cat/grep/jq |
| `claude-code-otel.raw` | 原始 OTLP JSON，可能有 null 填充字节，日常不用看 |

日常只看 `claude-code-otel.jsonl`：

```bash
cat "${AGENT_SERVICE_DATA_DIR:-$HOME/Documents/service-data}/otel/claude-code-otel.jsonl"
```

## 当前版本实际可用的事件（v2.1.92）

Claude Code v2.1.92 实际只输出以下两类 OTel log 事件：

| 事件名 | 内容 |
|---|---|
| `user_prompt` | 用户输入元数据（prompt 内容被 `<REDACTED>`，只有长度） |
| `api_request` | API 调用元数据（model、input/output tokens、cache tokens、cost_usd、duration_ms） |

**不包含 request/response payload**。`prompt` 字段始终为 `<REDACTED>`，这是 Claude Code 的安全限制。

```bash
# 查看 api_request（model、tokens、cost、duration）
grep 'api_request' "${AGENT_SERVICE_DATA_DIR:-$HOME/Documents/service-data}/otel/claude-code-otel.jsonl" | jq .

# 查看 user_prompt
grep 'user_prompt' "${AGENT_SERVICE_DATA_DIR:-$HOME/Documents/service-data}/otel/claude-code-otel.jsonl" | jq .

# 按 model 过滤
grep '"model"' "${AGENT_SERVICE_DATA_DIR:-$HOME/Documents/service-data}/otel/claude-code-otel.jsonl" | jq '.resourceLogs[0].scopeLogs[0].logRecords[0].attributes[] | select(.key=="model")'
```

## 如果需要完整的 request/response payload

OTel 方案当前无法满足。可考虑：

1. **Claude Code `--debug` 模式**：输出 API 请求细节到 stdout
   ```bash
   claude --debug -p "your prompt"
   ```

2. **LiteLLM 侧日志**：LiteLLM 作为代理会看到完整请求/响应 body，可在 LiteLLM 配置中开启详细日志

## 清空日志

```bash
> "${AGENT_SERVICE_DATA_DIR:-$HOME/Documents/service-data}/otel/claude-code-otel.jsonl"
```
