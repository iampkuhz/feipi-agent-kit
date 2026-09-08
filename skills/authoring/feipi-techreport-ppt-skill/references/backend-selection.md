# Backend 边界

Backend 只把 Resolved Render Plan 写成 PPTX，不选择字体、字号、颜色、组件或布局。

## P0

默认使用 `adapters/pptxgenjs/backend.js`：

- 输入为 schema 校验后的 Render Plan；
- 将 EMU 转为 PptxGenJS 所需单位；
- 输出原生文本、形状、表格和连接线；
- 设置稳定语义对象名和 z-order；
- 禁止 autofit、未知样式 fallback 和整页图片；
- 后端兼容修复不得改变设计合同。

`helpers/pptx/compiler.js` 和旧 CLI 只是兼容入口，不是第二套 compiler。

## 官方 Presentations 能力

通用 PPTX 读取、写入、渲染、文件检查、PowerPoint 兼容性和通用编辑优先复用官方 Presentations skill。P1 新增官方 Artifact Tool adapter，并用同一 Render Plan 与 PptxGenJS 比较：

- geometry；
- 字体、字号、颜色；
- 原生文本/表格/图表/连接线；
- 对象名和可编辑性；
- PowerPoint 渲染结果。

达到 parity 后才切换默认 adapter。切换不允许重写 Design Token、Component/Layout Contract 或 Semantic Slide IR。

## 不允许的后端

- 整页截图、SVG 或位图伪装成可编辑 PPT；
- 读取用户 Downloads 中的外部 design kit；
- 通过 HTML/CSS 自由布局绕过合同；
- 后端自带字号或坐标 fallback；
- 为适配某个引擎而修改 `Kaiti SC` 视觉规范。
