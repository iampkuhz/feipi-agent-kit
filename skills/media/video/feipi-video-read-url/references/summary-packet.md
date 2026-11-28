# 有依据、有层次的摘要

宿主负责全文阅读、读图及语义审核，脚本负责编号、版式、引用和可确定的风险检查。新摘要使用 v2；v1 仅兼容历史调用。

1. 全文读取正文、字幕或ASR，实际读图并登记观察；按具体数字、对象或对比句补帧，不能在章节开头随便取一张。来源不清就保留疑点，不猜术语数字。
2. 运行 `python3 scripts/summary_packet.py prepare OUTPUT_DIR`，读取 `summary_sources.txt` 中全部来源。只选真实编号，不手抄原文。
3. 从 prepare 返回的 `summary_draft.template.json` 复制为 `summary_draft.json`，保留脚本填好的来源指纹和全部内容ID（包含已读但不保留的帧观察）。不要重新抄写ID列表。使用 Python json.load/json.dump 修改结构，避免字符串拼接丢逗号。写一次正文，使用以下有界结构。标题保留原有主题编号；不要为排版合并掉重要条件。资料短时重点1条即可，通常3条，最多5条。用原有条目ID选择重点，不另写一段未经核验的概述。

```json
{
  "schema": "feipi-summary-draft-v2",
  "source_digest": "prepare的实际回执",
  "reviewed_artifact_ids": ["asr", "frame-001-ocr", "frame-001-visual_observation"],
  "semantic_review": "all_units_checked",
  "risk_checks": ["numbers_and_units", "scope", "causality", "conditions", "asr_terms", "visual_limits"],
  "highlights": ["operation-light"],
  "sections": [{
    "title": "8. 灯光",
    "layout": "list",
    "items": [{
      "id": "operation-light", "label": "操作台补光", "category": "recommendation",
      "text": "作者建议吊柜下方增加灯带，减少操作台背光。",
      "detail": "不扩写成地柜下方也必须安装。",
      "evidence": ["asr:0287", "asr:0302"]
    }]
  }]
}
```

`sections[].layout` 只允许 list 或 comparison。list 用加粗标签和短主句，需要时用 detail 保存解释或条件；comparison 自动生成“选项／作者观点／条件与补充”三列表格，用于真实的方案、材料或做法比较。不要将全文塞进一个表格；比较视频通常应有表格，不存在比较则不要造选项。

`category` 为 detail/comparison/recommendation/reason/condition/uncertainty。`text` 是主信息，`detail` 可选，两者分别绑定同组证据；每项为单行且不超过240字符，长内容拆为实际独立的信息项，而非删掉条件。label是不超过40字的短名称。不要手写换行、表格管道符或HTML；加粗、表格、引用块及脚注由脚本生成。

不确定条目用 uncertainty，放在相关主题内，脚本以引用块紧邻显示。真正逐字引用可设置 `verbatim: true`，text必须原样出现在所引来源中；不能把自己的归纳标成作者原话。引用脚注显示时间点，逐句证据保存在覆盖清单，不让正文每条都背负一大串时间戳。最终文件只放可用的来源链接，不列读者拿不到的 asr.txt 相对路径。

## 必须完成的反向审核

先对每项 text 与 detail 逐句回看其 evidence 所指原文，再填写 risk_checks 和 all_units_checked；不能只读 sources 文件头部就凭记忆填编号。

不得把10个来源主题并成8节；保留免拉手、抽屉收纳等原有独立编号。若标题声称的数量与来源确实不一致，使用 numbering_uncertainty 指向实际解释差异的 uncertainty 条目ID，并在对应主题记录证据；不能用此字段替合并章节找理由。

逐项检查：

- numbers_and_units：数字、单位、公式是否真能从引用读出；90%不得补成90cm，“八十八十五”不得直接选成85cm。无法确认时正文不保留确定尺寸，改为同主题疑点。百分比只作有精确原句的verbatim或uncertainty，不能推成性能提升。
- scope：对象和范围是否保持一致；“吊柜下方”不得扩大为“吊柜地柜下方”。安装位置、对齐关系和家庭成员同样不能凭含糊近似音补齐；只保留能确认的功能关系，关键疑点就近说明。
- causality：不要把相邻陈述拼成新的因果，例如把不清楚的百分比解释成质感提升。
- conditions：材料、工艺比较保留适用条件、代价、预算、设备及例外；不把“多数家庭使用”改成“多数家庭价格可接受”。
- asr_terms：含糊的术语不能凭熟悉程度确认；可补针对性截图或回听，未解决就写疑点，不在正文确定改写再到末尾免责。
- visual_limits：几张采样图不能支持“视频仅展示某实物”“全片没有示意图”等概括。单张水槽图可描述外观，不能据此认证一体成型工艺、性能或安装质量。

逐项检查引用是否足以支持整句及detail，而非仅有主题词。重点从已审核条目中选择，不能挑未确认参数。脚本拦截可确定的数值/单位矛盾及采样越界措辞，其通过不代表语义自动合格。六项审核是内部动作，不要求在正文逐条重复免责声明或转写乱码。只展示影响理解与选择的疑点，同主题合并为短引用块；通用边界只说明一次。

4. 运行 `python3 scripts/summary_packet.py build OUTPUT_DIR summary_draft.json`；业务调用方提供 finalize 时直接交给 finalize，不重复构建。
Housing集成仅执行其finalize，不先跑通用build；两者共同受同一证据批次的两次构建上限约束。

5. 失败一次列全，集中修复一次；仍失败停止并报告准确状态。不能改来源、伪造编号、删除状态文件或换目录绕过次数。新来源必须重新prepare并读完变更。
