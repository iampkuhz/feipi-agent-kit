# 本地 oMLX 转写

## 模型与服务

| 质量档位 | oMLX 模型家族 | 自动策略 |
| --- | --- | --- |
| 默认、auto、fast | SenseVoiceSmall（sensevoicesmall） | 字幕优先，缺失时 ASR |
| accurate、高精度、高质量、准确、逐字 | Qwen3-ASR-1.7B | ASR 优先，失败后尝试平台字幕 |

所有来源的 `whisper` 模式统一通过 `scripts/lib/omlx_transcribe.sh` 调用本地 `/v1/audio/transcriptions`。模式名、`.whisper.wav` 和 `whisper_profile` 保留兼容含义，不再使用 whisper.cpp。

默认服务为 `http://127.0.0.1:8037/v1`，可以通过 `AGENT_OMLX_BASE_URL` 指定其他本机 HTTP(S) 端口；仅接受 localhost、127.0.0.1、::1。认证配置 `AGENT_OMLX_API_KEY`，不要将密钥写入仓库。请求不经过系统代理。

通过 `/v1/models` 发现实际 ID，匹配模型末段的家族名，忽略大小写和分隔符；允许 bf16、fp16、4bit、8bit 后缀。如 `mlx-community/SenseVoiceSmall`、`Qwen3-ASR-1.7B-bf16`。同一家族必须只有一个候选；缺失或歧义即失败，不替换为其他模型。

`scripts/install_deps.sh` 仅安装下载与音频工具，并检查 oMLX 服务和模型，不启动服务、不下载 ASR 模型、不修改用户服务配置。

```bash
bash <本 skill>/scripts/install_deps.sh --check --accurate
bash <本 skill>/scripts/extract_video_text.sh '<URL>' '<OUTPUT_ROOT>' auto --instruction '总结视频'
bash <本 skill>/scripts/extract_video_text.sh '<URL>' '<OUTPUT_ROOT>' auto --quality accurate
```

## 分块与时间精度

音频统一为 16kHz、单声道、16-bit PCM WAV，按不超过30秒连续块顺序请求。每块保留原始文字和来源时间范围；不携带上一块文字上下文。SenseVoice 控制标签从正文中移除。空块可以保留为空，全片为空则失败。

oMLX 当前接口的 `response_format` 不能保证返回 SRT，客户端请求 JSON 并自行以实际音频块起止构建 SRT/TXT。时间锚点只表示块范围，不能声称逐句或逐字对齐，也不能据此推断精确画面位置。来源状态必须说明模型、约30秒块级时间精度及识别风险；块边界可能切开词句，专名、数字仍需核验。

一次请求超时为180秒，模型列表检查为10秒；每块只请求一次，失败交回统一入口，不自动换模型、并发重跑或回退云端。所有块完成后原子发布 SRT/TXT，最后发布 `.asr.json` 完成记录；失败不交付半份新稿，也不覆盖已有完整结果。

## 缓存与来源

`.asr.json` 记录 schema、模型家族与实际 ID、档位、语言、音频 SHA256、分块时间与文字、SRT/TXT 校验和。仅匹配家族、档位、语言、音频指纹与 SRT 校验的结果可以离线复用。TXT 缺失或不完整时从完整 SRT 恢复。旧 `.meta`/whisper.cpp 缓存不满足合同，须使用新模型重新识别。

统一入口输出 `asr_backend=omlx`、`asr_model`、`asr_timestamps=audio_chunk`；取证 manifest 使用 `provenance=omlx` 并保留模型与时间精度。只有本次实际成功的 ASR 才能写入这些来源字段；字幕回退仍标为平台字幕。
