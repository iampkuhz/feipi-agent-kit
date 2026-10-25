# 摘要覆盖复核

适用于通用提取结果及其图文调用方。提取清单的 complete 只表示提取任务完成，不代表摘要充分。

本规范只定义跨领域的内容保真与证据复核。领域重点、专用字段、知识库结构、工作流和渠道回执由调用方 skill 定义；通用层不加载某个业务项目的规则，也不按领域预设摘要模板。

1. **先清点来源，再写摘要**：读完全部可用正文/字幕/ASR、已登记的 OCR 与视觉观察，按来源结构列出实质主题与子主题。详略由用户目标和来源内容决定，去掉重复表达，保留承载含义的细节；不能用一级标题代替项内信息。
2. **按需补证**：均匀6帧仅作首次定位。遇到名词误识别、数值冲突或文字与画面不一致时，围绕对应时间点补抽并实际读取关键画面；时间间隔依画面变化调整，单次最多24个新增点。可用 `extract_frames.py - NEW_DIR --base-dir OLD_DIR --times '10,15,20'`，从原清单直接读取原始访问链接、复制证据到新目录再追加，不经宿主复制签名 URL，不覆盖旧提取。新点仍不足则明确缺口，不猜名词、数字或论证关系。纯文字模式不能读取画面时说明限制。
3. **按内容类型保留细节**：论述保留观点、依据和结论之间的关系；教程保留前提、步骤、参数与注意事项；若来源包含方案比较或建议，则分别保留选项、特点/优缺点、推荐强度、理由、代价和适用条件。叙事、访谈等保留各自的事件或观点结构，不强行填充来源未涉及的比较字段。不能补常识来填满模板。画面与语音互补，冲突明确指出，关键内容附时间点/图号。
4. **反向复核**：对着来源清点逐项检查最终摘要，确认实质细节、论证关系和不确定性均得到适当呈现，同时检查有无无依据的新增内容或前后矛盾。未确认但有用的信息明确列为待核验，不能悄悄删除。复核后填写 `summary_coverage.json`；每个独立内容单元一项，不能用“该主题已覆盖”等口号代替细节。此清单是宿主阅读记录，不是自动语义判断。

来源已有编号时保留其层级，子主题在所属项内展开，不任意改变一级项数量。转写中的数字拆分、单位或含义不明确时，只在待核验中保留原句和时间点，正文不写推断值；尾随“待核验”也不能成为补单位、造区间、猜专名或增加价值判断的理由。不能把“常见选择”改写成“最优选择”。

```json
{
  "schema": "feipi-summary-coverage-v1",
  "reviewed_artifact_ids": ["asr", "frame-001-ocr", "frame-001-visual_observation"],
  "source_review": "full_available_text_and_images",
  "summary_review": "all_units_checked",
  "units": [{
    "id": "option-a-reason", "topic": "方案A的选择理由", "category": "reason",
    "evidence": [{"artifact_id": "frame-001-ocr", "quote": "来源中真实出现的连续文字"}],
    "summary_quote": "摘要中真实出现的连续文字"
  }]
}
```

`category` 为 detail/comparison/recommendation/reason/condition/uncertainty。`reviewed_artifact_ids` 必须列出所有非空内容 artifact（OCR/观察取 JSON 中的 text，空 text 不列）；evidence 引用其中真实连续片段。每项 `summary_quote` 必须实际出现在摘要，不能只在覆盖清单里写补充内容。清点多少项由来源决定，无固定项数或字数阈值。

```bash
python3 <本skill>/scripts/review_summary.py OUTPUT_DIR/extraction_manifest.json OUTPUT_DIR/summary.md OUTPUT_DIR/summary_coverage.json
```

脚本拒绝漏引内容文件、虚构来源片段、摘要缺失条目。返回报告绑定本次 manifest、来源、摘要和清单的 SHA-256；修改摘要后必须重新执行。它不能发现宿主根本没有清点的语义内容，不能据此宣称“无遗漏”或“所有画面已分析”。需要持久化的调用方应在写入前重新调用该校验，保留覆盖清单与报告；具体存储和交付策略由调用方管理。
