# 运行时环境

## 基础

- 系统 Node.js 18+、npm 和 Python 3；
- `ajv` 用于 schema 校验；
- `pptxgenjs` 用于 P0 backend；
- `zip/unzip` 用于 OpenXML postcheck。

```bash
cd skills/authoring/feipi-techreport-ppt-skill
python3 scripts/prepare_runtime.py
python3 scripts/prepare_runtime.py --check
node scripts/doctor.js --json
```

首次使用 Ajv/PPTX 编译能力时自动运行一次固定锁文件的 `npm ci --ignore-scripts --no-audit --no-fund --prefer-offline`。共享缓存位于 `$XDG_CACHE_HOME/feipi-agent-kit/ppt/`；未设置时，macOS 使用 `~/Library/Caches/feipi-agent-kit/ppt/`，其他系统使用 `~/.cache/feipi-agent-kit/ppt/`。以包清单内容、系统/架构、Node 主版本和 ABI 隔离；相同版本跨客户端复用。准备失败不发布缓存；不向技能目录写入依赖，不运行 `npm update` 或依赖全局 npm 包。doctor 和 runtime_capabilities 只检查已准备的缓存。

## 渲染优先级

macOS：PowerPoint 导出（若可自动化）→ QuickLook/CoreText → LibreOffice 对照。Linux 可使用 LibreOffice，但必须记录字体环境差异。

`Kaiti SC` 在 strict 目标环境必须可由 PowerPoint/CoreText 解析。LibreOffice/fontconfig 缺少该 macOS 字体时，不能把中文方框误判为 PowerPoint 字体缺失，也不能静默改成 Verdana。

## 能力声明

- 只有 schema/Static QA：不能声称 PPTX 已验证。
- 生成并通过 package QA：只能声称结构与编辑性自动门禁通过。
- 有渲染图片但未查看原图：不能声称视觉通过。
- strict 缺少权威渲染或 PowerPoint 编辑回环：状态为 `incomplete` 或明确报告验证边界。

视觉签字和 PowerPoint 编辑回环应在具备桌面环境的验收机执行。
