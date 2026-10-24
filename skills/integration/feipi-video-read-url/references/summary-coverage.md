# 摘要覆盖复核

适用于通用提取结果及其图文调用方。提取清单的 complete 只表示提取任务完成，不代表摘要充分。

1. **先清点来源，再写摘要**：读完全部可用正文/字幕/ASR、已登记的 OCR 与视觉观察，按原文顺序列出实质主题及子主题。编号教程保留每一项，并展开项内独立的材料、工艺、比较、建议、理由、代价、适用条件和限制；不能只保留一级标题。去掉重复口播，不以字数、列表项数或 Telegram 回执长度压掉决策信息。
2. **按需补证**：均匀6帧仅作首次定位。遇到技术名词误识别、参数冲突、“几种/优缺点/推荐/预算”等比较段落，围绕对应时间点补抽并实际读取说明卡片，通常间隔2–5秒；最多24个新增点。可用 `extract_frames.py - NEW_DIR --base-dir OLD_DIR --times '142,145,150'`，从原清单直接读取原始访问链接、复制证据到新目录再追加，不经宿主复制签名 URL，不覆盖旧提取。新点仍不足则明确缺口，不猜术语、数字或比较理由。纯文字模式不能读取画面时说明限制。
3. **保留决策内容**：每个比较方案分别记录特点/优缺点、作者建议及理由、价格/设备/地区/预算等条件。原文未给理由就写“未说明”，不能补常识。技术细节在完整笔记中单列子标题或表格；例如封边工艺不能埋在“材质选择”一句话里。画面与语音互补，冲突明确指出，来源逐项附时间点/图号。
4. **反向复核**：对着来源清点逐项检查最终摘要，确认比较选项、推荐强度、理由、适用条件和不确定性都保留。未确认的有用信息在摘要明确列为待核验，不能悄悄删除。复核后填写 `summary_coverage.json`；每个独立内容单元一项，不能用“材质已覆盖”等主题口号代替细节。此清单是宿主阅读记录，不是自动语义判断。

编号教程沿用来源一级编号，独立子主题在该项内部用子标题或表格展开，不把11条改成12条。转写中的数字拆分、单位或含义不明确时，只在待核验中保留原句和时间点，正文不写推断数值；尾随“待核验”也不能成为补单位、造区间、猜品牌或增加价格判断的理由。比如“多数家庭使用”不能改成“多数家庭价格可接受”。最终复核既查遗漏，也查新增内容是否有证据、前后是否矛盾。

```json
{
  "schema": "feipi-summary-coverage-v1",
  "reviewed_artifact_ids": ["asr", "frame-001-ocr", "frame-001-visual_observation"],
  "source_review": "full_available_text_and_images",
  "summary_review": "all_units_checked",
  "units": [{
    "id": "option-a-reason", "topic": "工艺A的选择理由", "category": "reason",
    "evidence": [{"artifact_id": "frame-001-ocr", "quote": "来源中真实出现的连续文字"}],
    "summary_quote": "摘要中真实出现的连续文字"
  }]
}
```

`category` 为 detail/comparison/recommendation/reason/condition/uncertainty。`reviewed_artifact_ids` 必须列出所有非空内容 artifact（OCR/观察取 JSON 中的 text，空 text 不列）；evidence 引用其中真实连续片段。每项 `summary_quote` 必须实际出现在摘要，不能只在覆盖清单里写补充内容。清点多少项由来源决定，无固定11项或字数阈值。

```bash
python3 <本skill>/scripts/review_summary.py OUTPUT_DIR/extraction_manifest.json OUTPUT_DIR/summary.md OUTPUT_DIR/summary_coverage.json
```

脚本拒绝漏引内容文件、虚构来源片段、摘要缺失条目。返回报告绑定本次 manifest、来源、摘要和清单的 SHA-256；修改摘要后必须重新执行。它不能发现宿主根本没有清点的语义内容，不能据此宣称“无遗漏”或“所有画面已分析”。集成方应在写入前重新调用该校验，保留覆盖清单与报告。摘要较长时 Telegram 仅作回执，并链接完整笔记，不能用短回执替代入库摘要。
