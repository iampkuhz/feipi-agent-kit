# 本地 oMLX 转写

## 模型与服务

| 质量档位 | oMLX 模型家族 | 自动策略 |
| --- | --- | --- |
| 默认、auto、fast | SenseVoiceSmall（sensevoicesmall） | 字幕优先，缺失时 ASR |
| accurate、高精度、高质量、准确、逐字 | Qwen3-ASR-1.7B | ASR 优先，失败后尝试平台字幕 |

`accurate` 是模型选择档位，不表示权重使用更高的数值精度，也不保证每段音频的字错率都更低。Qwen3-ASR-1.7B 可提供 BF16、4bit、8bit 等版本，实际使用哪种版本以服务模型 ID 为准；磁盘体积同时取决于参数量、量化位宽和未量化组件，不能只按文件大小判断速度或识别质量。运行时不自动替换服务中已有的权重版本。

所有来源的 `whisper` 模式统一使用 `scripts/lib/omlx_transcribe.py`（站点通过同名 `.sh` 包装器）调用本地 `/v1/audio/transcriptions`。本地文件由 `read_local_media.py` 提取首条完整音轨后复用该客户端；没有平台字幕回退。模式名、`.whisper.wav` 和 `whisper_profile` 保留兼容含义，不再使用 whisper.cpp。

默认服务为 `http://127.0.0.1:8037/v1`，可以通过 `AGENT_OMLX_BASE_URL` 指定其他本机 HTTP(S) 端口；仅接受 localhost、127.0.0.1、::1。认证仅通过 `os.environ` 读取 `OMLX_API_KEY`，有值时添加 Bearer 请求头；变量缺失时不从文件补读。skill 不读取 `~/.env` 或其他 dotenv 文件，不主动执行 shell 启动文件，不输出密钥，也不将其写入仓库。请求不经过系统代理。

环境变量应由调用方传入。终端中的 Codex CLI 继承启动它的 shell 已导出的变量；Codex 桌面端应以当前命令环境是否含有该变量为准，不能假设每条命令都会重新执行 `.zshrc`。排查时仅检查变量是否存在，不打印其值；HTTP 401 提示检查 `OMLX_API_KEY`，不展示配置内容。

通过 `/v1/models` 发现实际 ID，匹配模型末段的家族名，忽略大小写和分隔符；允许 bf16、fp16、4bit、8bit 后缀。如 `mlx-community/SenseVoiceSmall`、`Qwen3-ASR-1.7B-bf16`。同一家族必须只有一个候选；缺失或歧义即失败，不替换为其他模型。

`scripts/install_deps.sh` 仅安装下载与音频工具，并检查 oMLX 服务和模型，不启动服务、不下载 ASR 模型、不修改用户服务配置。

```bash
bash <本 skill>/scripts/install_deps.sh --check --accurate
bash <本 skill>/scripts/extract_video_text.sh '<URL>' '<OUTPUT_ROOT>' auto --instruction '总结视频'
bash <本 skill>/scripts/extract_video_text.sh '<URL>' '<OUTPUT_ROOT>' auto --quality accurate
```

## 分块与时间精度

音频统一为 16kHz、单声道、16-bit PCM WAV，由 `scripts/lib/split_audio.py` 规划停顿切口，再按连续、无重叠的块顺序请求。默认上限30秒，在该段最后三分之一（默认第20–30秒）内寻找音量不高于-35dBFS、持续至少250ms的停顿，优先取靠后停顿的中点，为前后语音留出余量；切口约束在搜索窗口、分块上限和静音两端至少30ms以内。长静音已覆盖搜索窗口时尽量保留长块。找不到合适停顿则按上限强制切开，最后不足上限的部分直接保留，包括很短的尾部。停顿检测不理解句义，也不能保证所有切口都避开词语。

切分只保留一个可调配置 `--max-seconds`，默认/推荐30秒；静音阈值与搜索比例为内部常量，不提供试听模式、播放参数或额外模型。切分不删除静音、不制造重叠，因此所有采样只出现一次；避免重叠块在没有可靠文本对齐时产生重复转写。每块保留原始文字、来源时间范围和 `cut_reason=pause|forced|end`，不携带上一块文字上下文。SenseVoice 控制标签从正文中移除。空块可以保留为空，全片为空则失败。

统一 URL 与本地文件链路自动使用默认30秒。需要单独检查切分结果时，执行下面的独立脚本；它将 WAV、`cuts.csv`、`manifest.json` 写到输入音频旁的新目录，并逐段打印文件和原始时间，不调用 ASR、不自动播放：

```bash
python3 <本 skill>/scripts/lib/split_audio.py '<AUDIO.wav>' --max-seconds 30
```

可将上限改为60秒；搜索范围自动变为第40–60秒。例如停顿从第56秒持续到第63秒，切口为约59.5秒。低层 `omlx_transcribe.py` 同样接受 `--max-seconds`；模型、语言与认证仍由既有参数和进程环境决定。默认仍推荐30秒，其他上限的程序完整性检查不代表识别质量已经验证。

oMLX 当前接口的 `response_format` 不能保证返回 SRT，客户端请求 JSON 并自行以实际音频块起止构建 SRT/TXT。时间锚点只表示块范围，不能声称逐句或逐字对齐，也不能据此推断精确画面位置。来源状态必须说明模型、约30秒块级时间精度及识别风险；块边界可能切开词句，专名、数字仍需核验。

一次请求超时为180秒，模型列表检查为10秒；每块只请求一次，失败交回统一入口，不自动换模型、并发重跑或回退云端。所有块完成后原子发布 SRT/TXT，最后发布 `.asr.json` 完成记录；失败不交付半份新稿，也不覆盖已有完整结果。

成功日志中的 `asr_elapsed_seconds` 使用单调时钟记录 ASR 客户端耗时，包括音频校验与停顿切分、模型发现、模型首次加载、所有分块请求及结果落盘，不含平台下载和前置 ffmpeg 格式转换。缓存命中时该值表示缓存检查耗时；比较实际识别速度必须同时确认 `cache_reused=0`。

## 缓存与来源

`.asr.json` 记录 schema、模型家族与实际 ID、档位、语言、音频 SHA256、分块策略和上限、分块采样起止、时间与文字、SRT/TXT 校验和。仅匹配家族、档位、语言、音频指纹、分块策略/上限，且连续采样范围覆盖全片、分块正文与 SRT/TXT 校验一致的结果可以离线复用。schema 保持 `omlx-asr-v2`，策略更新为 `chunk_policy=pause-center-v2`；旧 `pause-start-v1`、固定切分和不同上限的结果不能复用。TXT 缺失或不完整时从校验通过的分块正文原子恢复。旧 `.meta`/whisper.cpp 缓存不满足合同，须使用新模型重新识别。

摘要请求复用同一缓存校验函数，只读检查 SRT/TXT 与分块来源；不修复、不触发 ASR。缓存来源校验不通过时明确披露，不能只凭旁边存在 JSON 就声称已验证模型或时间精度。本地 `source_media.json` 另外保留原件到音频的指纹链；ASR 缓存绑定提取音频的 SHA256。程序校验只证明采样完整和来源一致，真实识别结果与参考稿比较、人工听感须分别报告。

统一入口输出 `asr_backend=omlx`、`asr_model`、`asr_timestamps=audio_chunk`；认证来源仅输出 `asr_auth=env:OMLX_API_KEY` 或 `none`，不包含密钥。缓存命中时输出 `asr_auth=not_requested_cache`、`cache_reused=1`，不能据此声称本次发起了认证或模型推理。取证 manifest 使用 `provenance=omlx` 并保留模型与时间精度。只有实际成功的 ASR 才能写入这些来源字段；字幕回退仍标为平台字幕。
