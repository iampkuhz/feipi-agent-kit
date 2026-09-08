# 运行时环境

## 基础

- Node.js 与 skill 本地 `npm ci`；
- `ajv` 用于 schema 校验；
- `pptxgenjs` 用于 P0 backend；
- `zip/unzip` 用于 OpenXML postcheck。

```bash
cd skills/authoring/feipi-techreport-ppt-skill
npm ci
node scripts/doctor.js --json
```

## 渲染优先级

macOS：PowerPoint 导出（若可自动化）→ QuickLook/CoreText → LibreOffice 对照。Linux 可使用 LibreOffice，但必须记录字体环境差异。

`Kaiti SC` 在 strict 目标环境必须可由 PowerPoint/CoreText 解析。LibreOffice/fontconfig 缺少该 macOS 字体时，不能把中文方框误判为 PowerPoint 字体缺失，也不能静默改成 Verdana。

## 能力声明

- 只有 schema/Static QA：不能声称 PPTX 已验证。
- 生成并通过 package QA：只能声称结构与编辑性自动门禁通过。
- 有渲染图片但未查看原图：不能声称视觉通过。
- strict 缺少权威渲染或 PowerPoint 编辑回环：状态为 `incomplete` 或明确报告验证边界。

CI 应运行 `bash scripts/test.sh`；视觉签字和 PowerPoint 编辑回环可在具备桌面环境的验收机执行。
