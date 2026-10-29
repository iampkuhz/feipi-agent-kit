# 字幕驱动的有限选帧

初次只截00:00首帧。实际读首帧和全部字幕／ASR后选择0–5个额外时间点。允许0张，不等间隔、不凑数量，不下载整片。

## 用编号选择具体证据句

```bash
python3 scripts/frame_plan.py prepare INITIAL_OUTPUT_DIR
```

读取实际回执 frame_sources.txt。选择需要核验的数字、术语、对象或对比**出现的那一句**，不是章节开头。例如核验台面高度不能只选“下面讲高低台”；核验超白玻不能选前一分钟“选地轨门”。先考虑截图是否可能提供文字之外的信息，再决定。

写 selections.json：

```json
{
  "decision": "已读全文；选择两个具体疑点，其余文字足够。",
  "frames": [{
    "source_id": "asr:0212",
    "key_text": "90%",
    "title": "洗菜区高度核验",
    "question": "转写把高度识别成百分比，画面字幕或标注能否确认实际数字与单位？"
  }]
}
```

source_id来自实际编号；key_text必须在该行原文中，question具体说明需看见什么。编号自动生成精确时间、原文引用与来源哈希，无须手写这些内容。无可靠文字时只能frames空列表。

```bash
python3 scripts/frame_plan.py build INITIAL_OUTPUT_DIR selections.json
python3 scripts/extract_frames.py - NEW_OUTPUT_DIR --base-dir INITIAL_OUTPUT_DIR --plan INITIAL_OUTPUT_DIR/frame_plan.json
```

Housing调用方也可使用 `housing_tool.py --repo-root REPO extract --record ID --output-dir NEW_OUTPUT_DIR --base-dir INITIAL_OUTPUT_DIR --plan INITIAL_OUTPUT_DIR/frame_plan.json`。以回执manifest为准，实际读新增图片，登记观察，再决定保留或排除。计划的期望不能冒充实际看见的内容。

首帧不重复截取。累计最多5个额外时间点，失败点仍占预算，可重试同一点，不因排除或新目录重置预算。无法确认的疑点保留，不盲目追加截图。最终图片是否有意义仍需实际读图后审核，不能把采样覆盖外推整片。

底层仍接受frame_plan v1供历史兼容，但新任务使用上述编号入口，避免原文前缀、跨行引用和时间窗错误。
