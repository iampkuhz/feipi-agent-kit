# 本地媒体回归样例

`speech.m4a` 为41秒、265330字节的普通话合成语音。先编写 `reference.txt`，再使用 macOS 自带 Tingting 语音生成音频；不从 ASR 结果倒推参考稿。文件哈希与生成参数见 `metadata.json`。

生成方式（仅重新制作 fixture 时需要 macOS；日常测试只读取固定文件）：

```bash
say -v Tingting -r 175 -f reference.txt -o /tmp/feipi-reference.aiff
ffmpeg -nostdin -v error -y -i /tmp/feipi-reference.aiff -ac 1 -ar 16000 -c:a aac -b:a 48k speech.m4a
```

`tests/test_local_media.py` 将音轨原样封装进静态视频，实际调用统一入口提取 WAV，再检查整条音轨与不同上限下的采样完整性。默认程序检查不访问 ASR，不能作为识别正确的证据。生成的视频、提取音频和运行日志均写临时目录；`tests/` 不安装到日常 skill。

真实 oMLX 集成回归：从仓库根目录执行下列命令，调用方须已通过进程环境传入 `OMLX_API_KEY`（如服务要求认证）。脚本不读取 dotenv，不显示密钥，不安装模型。

```bash
FEIPI_OMLX_LIVE_TEST=1 \
FEIPI_OMLX_TEST_OUTPUT=tmp/skill-evals/feipi-video-read-url/local-live \
python3 skills/integration/feipi-video-read-url/tests/test_local_media.py
```

该测试在默认30秒上限下分别运行 SenseVoiceSmall 和 Qwen3-ASR-1.7B，断言分成两块且真实 ASR 与参考稿的162个正文汉字逐字一致。只忽略标点和空白，不替换同音字、不补字、不改繁简。模型升级或识别差异导致不一致时测试必须失败。`real-asr-results.json` 保存逐字对照、模型和缓存状态；`cache_reused=1` 只证明已有结果复用，首次真实推理证据须为0。

合成样例只验证固定语音的回归与流程，不代表自然长音频的通用识别质量。未进行人工听感评估；原42分钟音频无人工参考稿，不计算准确率百分比。
