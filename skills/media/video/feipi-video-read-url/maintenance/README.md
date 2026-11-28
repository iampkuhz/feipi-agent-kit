# 维护入口

- `SKILL.md` 负责视频与本地音频任务入口及转写策略；`references/omlx-asr.md` 维护 oMLX 接口、默认地址、认证和固定模型约定。
- `scripts/lib/omlx_transcribe.py` 是站点与本地媒体共用的 HTTP 转写客户端。
- `agents/openai.yaml` 保存分发版本与触发提示。端口或转写行为变化时同步检查入口、参考文档、客户端和工作台 oMLX 服务配置。
