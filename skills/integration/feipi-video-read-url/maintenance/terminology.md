# 术语

- oMLX：本机推理服务；本 Skill 通过 OpenAI 兼容接口读取模型并请求语音转写。
- 服务基址：包含本机主机、端口和 `/v1` 的 API 根地址，由 `AGENT_OMLX_BASE_URL` 覆盖默认值。
- 转写模型：所有语音转写请求固定使用 `Qwen3-ASR-1.7B-8bit`。
