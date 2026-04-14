# Model Scripts

模型管理相关脚本。

## download_hf_model.sh

从 Hugging Face 下载模型并导入指定目录（如 OMLX 模型路径）。

### 前置依赖

```bash
pip install huggingface_hub[cli]
```

### 基本用法

```bash
# 通过本地代理下载模型到 OMLX 路径
bash scripts/model/download_hf_model.sh \
  -p http://127.0.0.1:7890 \
  -o /Users/zhehan/Library/Containers/com.apple.OMLLMApp/Data/models \
  Qwen/Qwen2.5-7B-Instruct

# 仅下载 GGUF 量化文件
bash scripts/model/download_hf_model.sh \
  -p http://127.0.0.1:7890 \
  --include '*Q4_K_M*' \
  bartowski/Llama-3.2-3B-Instruct-GGUF

# 查看帮助
bash scripts/model/download_hf_model.sh --help
```

### 下载后验证

脚本自动验证：
- 文件非空
- 列出关键模型文件（`.safetensors` / `.gguf` / `.bin` / `config.json`）
- 显示目录大小
