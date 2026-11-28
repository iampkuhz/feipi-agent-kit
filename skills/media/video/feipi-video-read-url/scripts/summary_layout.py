#!/usr/bin/env python3
"""有界摘要版式与风险检查；引用可追溯不替代宿主语义复核。"""
import re

CHECKS = {"numbers_and_units", "scope", "causality", "conditions", "asr_terms", "visual_limits"}
MEASURE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(mm|cm|m2|m²|㎡|m|毫米|厘米|公分|米|平方米|平方|℃|K)(?![A-Za-z])", re.I)
UNITS = {"毫米":"mm", "厘米":"cm", "公分":"cm", "米":"m", "平方米":"m2", "平方":"m2", "㎡":"m2", "m²":"m2"}


def normalized(text):
    # 只做可逆的常用数字及单位同义归一化，不把百分号猜成长度。
    digits = dict(zip("零一二三四五六七八九", range(10)))
    def number(m):
        s=m[0].replace("两","二")
        if "百" in s or "千" in s: return s
        if "十" in s:
            left,right=s.split("十",1)
            return str((digits.get(left,1) if left else 1)*10 + digits.get(right,0))
        return "".join(str(digits[c]) for c in s)
    text=re.sub(r"[零一二两三四五六七八九十]+(?=毫米|厘米|公分|米|平方|℃|K)",number,text)
    for old,new in sorted(UNITS.items(), key=lambda x:-len(x[0])): text=text.replace(old,new)
    return re.sub(r"\s+","",text).lower()


def check_claim(item, rows):
    text = item["text"] + " " + item.get("detail", "")
    source = "\n".join(r["quote"] for r in rows)
    errors=[]
    if re.search(r"(?:视频|全片|整片|整段).{0,15}(?:仅|只有|没有).{0,12}(?:展示|画面|实物|图示)",text):
        errors.append("sampled_images_cannot_prove_whole_video:"+item["id"])
    if item.get("verbatim") and item["text"] not in source:
        errors.append("verbatim_quote_not_in_source:"+item["id"])
    if item["category"] != "uncertainty":
        if re.search(r"\d+(?:\.\d+)?\s*[%％]",text) and not item.get("verbatim"):
            errors.append("percentage_requires_verbatim_or_uncertainty:"+item["id"])
        source_measures={normalized(v+u) for v,u in MEASURE.findall(normalized(source))}
        for value,unit in MEASURE.findall(text):
            claim=normalized(value+unit)
            if claim not in source_measures:
                errors.append("measurement_not_explicit_in_evidence:"+item["id"]+":"+value+unit)
    return errors


def render(manifest, draft, packet, anchor_text):
    errors=[]; units=[]; ordered=[]; ids=set(); sections=[]
    if set(draft.get("risk_checks", [])) != CHECKS: errors.append("six_semantic_risk_checks_required")
    for section in draft.get("sections", []):
        title=section.get("title", ""); layout=section.get("layout", "list")
        if not isinstance(title,str) or not title.strip() or "\n" in title or layout not in {"list","comparison"}:
            errors.append("invalid_editorial_section");continue
        rows=[]
        for item in section.get("items", []):
            key=item.get("id");text=item.get("text");label=item.get("label");detail=item.get("detail","")
            if not isinstance(key,str) or not key or key in ids:
                errors.append("invalid_summary_unit_id");continue
            ids.add(key)
            if (any(not isinstance(x,str) or "\n" in x or "|" in x or "<" in x or ">" in x for x in [text,label,detail])
                    or not text.strip() or not label.strip() or len(label)>40 or len(text)>240 or len(detail)>240):
                errors.append("invalid_editorial_unit:"+key);continue
            if item.get("category") not in {"detail","comparison","recommendation","reason","condition","uncertainty"}:
                errors.append("invalid_summary_unit:"+key);continue
            refs=item.get("evidence")
            if not isinstance(refs,list) or not refs or any(not isinstance(x,str) or x not in packet["segments"] for x in refs):
                errors.append("unknown_evidence_id:"+key);continue
            evidence=[packet["segments"][x] for x in refs]
            errors.extend(check_claim(item,evidence))
            number=len(ordered)+1
            item={**item,"number":number,"rows":evidence};rows.append(item);ordered.append(item)
            # 正文与补充说明分别绑定证据，不能只验证主句而漏掉条件。
            for suffix,quote in [("",text),("-detail",detail)]:
                if quote:units.append({"id":key+suffix,"topic":title,"category":item["category"],"summary_quote":quote,
                    "evidence":[{"artifact_id":r["artifact_id"],"quote":r["quote"]} for r in evidence]})
        if not rows:errors.append("section_items_required:"+title)
        sections.append((title,layout,rows))
    if not ordered or len(ordered)>150:errors.append("invalid_summary_unit_count")
    if any(re.fullmatch(r"(?:\d+[.、 ]*)?待核验", title.strip()) for title, _, rows in sections if rows):
        errors.append("place_uncertainties_next_to_related_topic_not_global_dump")
    by_id={x["id"]:x for x in ordered}
    selected=draft.get("highlights")
    if not isinstance(selected,list) or not 1<=len(selected)<=5 or len(set(selected))!=len(selected) or any(x not in by_id for x in selected):
        errors.append("choose_one_to_five_existing_highlight_ids");selected=[]
    elif any(by_id[x]["category"]=="uncertainty" or by_id[x].get("verbatim") for x in selected):
        errors.append("uncertain_or_verbatim_claim_cannot_be_highlight")
    title = str(manifest.get("metadata", {}).get("title") or "")
    numbered = re.search(r"(\d+)(?:个|条|种)(?:设计|方法|建议|技巧|要点|避坑)", title)
    if numbered:
        expected = int(numbered[1])
        actual = [t for t, _, rows in sections if any(x["category"] != "uncertainty" for x in rows)]
        note_id = draft.get("numbering_uncertainty")
        if len(actual) != expected and (not isinstance(note_id, str) or note_id not in by_id or by_id[note_id]["category"] != "uncertainty"):
            errors.append("source_numbering_must_be_preserved_or_explicitly_unresolved")
    if selected and sum(len(by_id[k]["text"])+len(by_id[k]["label"]) for k in selected if k in by_id)>360:
        errors.append("highlights_too_long_move_explanation_to_detail")
    if errors:raise ValueError("\n".join(errors))
    lines=["## 摘要概述","",str(manifest.get("metadata",{}).get("title") or "来源内容"),"",
           "> **阅读说明**：以下为来源作者的观点与做法；采样画面仅说明对应时间点。未确认的信息就近标注，不作为已确定方案。","","### 先看重点",""]
    for key in selected:
        row=by_id[key];lines.append(f'- **{row["label"]}**：{row["text"]} [^{row["number"]}]')
    for title,layout,rows in sections:
        lines += ["","### "+title,""]
        normal=[x for x in rows if x["category"]!="uncertainty" and not x.get("verbatim")]
        if layout=="comparison" and normal:
            lines += ["| 选项 | 作者观点 | 条件与补充 |","| --- | --- | --- |"]
            for row in normal:lines.append(f'| **{row["label"]}** | {row["text"]} [^{row["number"]}] | {row.get("detail") or "来源未说明更多条件。"} |')
        else:
            for row in normal:
                lines += [f'- **{row["label"]}**：{row["text"]} [^{row["number"]}]']
                if row.get("detail"):lines += ["","  补充："+row["detail"],""]
        for row in rows:
            if row["category"]=="uncertainty" or row.get("verbatim"):
                tag="待核验" if row["category"]=="uncertainty" else "来源原话"
                lines += ["",f'> **{tag} · {row["label"]}**：{row["text"]} [^{row["number"]}]']
                if row.get("detail"):lines += ["> "+row["detail"]]
    frames=[a for a in manifest["artifacts"] if a["kind"] in {"image","frame"}]
    kinds=sorted({a["kind"] for a in manifest["artifacts"] if a["kind"] in {"body","asr","subtitles"}})
    names={"asr":"语音转写（ASR）", "subtitles":"字幕", "body":"正文"}
    states={"complete":"完成", "partial":"部分完成", "failed":"失败", "unavailable":"不可用"}
    text_status="、".join(names[k]+"："+states.get(manifest.get("channels",{}).get(k,{}).get("status"),"未说明") for k in kinds)
    def seconds(anchor):
        values=[int(x) for x in anchor.split(":")]
        return sum(n*60**i for i,n in enumerate(reversed(values)))
    times=sorted({anchor_text(r) for r in packet["segments"].values() if re.search(r"\[\d{2}:\d{2}(?::\d{2})?\]",r["quote"])},key=seconds)
    timeline=(times[0]+"–"+times[-1]+"；保留时间戳") if len(times)>1 else (times[0] if times else "来源无逐段时间戳")
    lines += ["","## 来源状态","",f'- 文字提取：{text_status}；{timeline}。',
              f'- 画面：已读采样图片 {len(frames)} 张，不代表全片画面覆盖。',
              "- 未使用外部资料；自动转写中的专名、数字和条件按上述待核验项处理。","","### 引用",""]
    url=manifest.get("canonical_url") or manifest["original_url"]
    for row in ordered:
        anchors=list(dict.fromkeys(anchor_text(x) for x in row["rows"]))
        timed=sorted((x for x in anchors if re.fullmatch(r"\d{2}:\d{2}(?::\d{2})?",x)),key=seconds)
        # 正文给易读的定位范围；逐条精确引用仍保存在覆盖清单。
        locations=([timed[0]+"–"+timed[-1]] if len(timed)>1 else timed)+[x for x in anchors if x not in timed]
        lines.append(f'[^{row["number"]}]: {"、".join(locations)}。')
    lines += ["","## 附件","",f'[原始来源]({url})']
    return "\n".join(lines)+"\n", units
