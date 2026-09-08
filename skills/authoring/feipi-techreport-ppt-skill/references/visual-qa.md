# 真实视觉 QA

自动脚本退出码不能替代对真实渲染图的检查。正式页面至少完成以下证据链。

## 1. Static QA

- 元素和 region 越界；
- text-to-text overlap、脚注碰撞、连接线穿字；
- 估算截断和容量超载；
- 按 `text_role` 校验离散字号与 minimum。

## 2. Package / Editability QA

- PPTX 可解包且关系完整；
- 不含 `spAutoFit` 或 `normAutofit`；
- 所有字号可反查 token；
- `cNvPr id` 唯一；对象名唯一且具有 `feipi__` 语义前缀；
- 主要元素为原生 text/shape/table/connector/chart；
- 不是整页图片，不把整页组合成单一难编辑对象；
- table/chart 数据和内部文字保持可编辑。

## 3. 权威渲染

macOS 优先级：PowerPoint 导出 → QuickLook/CoreText → LibreOffice 对照。LibreOffice 不能解析 macOS 字体时只记录兼容 warning，不据此改变最终字体。

逐页查看全尺寸原图，检查：

- 标题、页眉、主视觉、证据和脚注是否清晰分层；
- 是否存在重叠、裁剪、越界、中文缺字或异常换行；
- 连接线与节点关系是否明确；
- 表格是否可读；
- 页面是否一眼先看到结论；
- 跨页字体、颜色、间距和组件风格是否一致。

montage 只用于跨页一致性，不能替代逐页原图检查。

## 4. 编辑回环

strict 交付时对临时副本执行：编辑文字、移动一个组件、修改表格单元格（适用时）、保存、关闭并重新打开。记录成功项和环境限制。

## 判定

- 任一明显重叠、截断、越界、缺字或包结构错误：`fail`。
- 需要拆页、删除重要内容或改变业务含义：`needs_user_decision`。
- strict 缺少权威渲染或编辑回环：`incomplete`，不能声称完整验收通过。
- 所有自动检查通过但尚未查看原图：只能报告自动门禁通过。
