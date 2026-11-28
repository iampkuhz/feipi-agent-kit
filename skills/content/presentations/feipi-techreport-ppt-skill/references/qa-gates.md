# QA 门禁

## Gate A：输入结构

- v2 schema 通过；
- component/layout/variant/size/region 引用存在；
- 独立文本有 `text_role`；
- 普通模式无 style 或自由几何；
- custom-grid 只使用整数 12 列网格；
- 来源引用合法。

## Gate B：编译确定性

- 所有视觉值来自 TokenStore；
- 所有组件和 slot 样式来自合同；
- 每个文本角色使用登记的离散字号且不低于该角色 minimum；
- 同输入 geometry hash 一致；
- overflow 不生成新字号；
- solver 不覆盖合法合同结果。

## Gate C：Static QA

- 无 text-to-text overlap、脚注碰撞、截断和越界；
- 连接线不穿过非端点文本；
- region 容量和内容容量满足合同；
- 超载返回固定 overflow action。

## Gate D：PPTX Package / Editability

- OpenXML 关系和 slide count 正确；
- 无 autofit、重复 ID、未登记字号或匿名关键对象；
- 主要元素是原生可编辑对象；
- 没有整页图片；
- 连接线和对象名称保留语义关系。

## Gate E：Render QA

- 使用 PowerPoint/QuickLook 优先渲染；
- 查看逐页全尺寸图；
- 无明显重叠、裁剪、越界、缺字、换行异常；
- 主视觉、证据、结论和脚注层级清晰；
- montage 跨页风格一致。

## Gate F：Strict 编辑回环

- 临时副本可在 PowerPoint 打开；
- 文字、组件、表格单元格（适用时）可独立编辑；
- 保存并重开成功；
- 变更不会把整页破坏为不可维护对象。

## 状态与严重性

| 状态 | 含义 |
|---|---|
| `pass` | 当前模式要求的自动门禁通过；正式交付仍需记录实际视觉检查 |
| `needs_user_decision` | 拆页、删除重要内容或业务含义取舍 |
| `fail` | 任一结构、编译、包、编辑性或视觉 hard fail |
| `incomplete` | strict 缺少权威渲染或编辑回环证据 |

warning 必须描述具体限制，不能把“图片存在且比例正常”当作 Render QA 通过。
