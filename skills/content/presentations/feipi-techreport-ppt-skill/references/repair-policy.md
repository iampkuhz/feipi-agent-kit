# Overflow 与修复策略

Pipeline 检测问题并返回结构化状态，不静默改写业务内容，也不自动生成新字号。

固定动作顺序：

1. `compress_text`：删除重复表述、合并同义信息；
2. `change_component_size`：切换登记的离散 size；
3. `change_layout`：选择容量更合适的登记 Layout；
4. `drop_secondary`：移除次要内容；重要内容需要用户确认；
5. `split_required`：拆页，需要用户确认。

## 禁止

- 连续缩小字体、二分搜索字号或 PowerPoint autofit；
- 低于 text role minimum；
- 移动到任意坐标绕过 Layout Contract；
- 删除重要事实、修改数字或改变业务含义；
- 对相同 IR hash 重复运行并声称已修复。

## 问题归属

| 问题 | 应修改层 |
|---|---|
| 重复或过长表述 | Composition / IR content |
| 组件容量不足 | Component Contract size/overflow 或 IR size |
| 页面认知任务不匹配 | Layout Contract 或 IR layout_id |
| 任意字号/颜色 | Schema/validator 拒绝 |
| token 缺失 | TokenStore/Design Token |
| 元素重叠、截断、越界 | Compiler/Layout Contract/QA |
| PPTX 包、对象名或编辑性 | Backend/Postcheck |

任何“修复后重跑”都必须形成新的 IR 或合同版本，并产生新的 hash。
