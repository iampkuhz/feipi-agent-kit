# Expected Checks: P0-03

## Must

- [ ] 页面只有 1 页。
- [ ] 包含用户/DApp、HostChain、Coprocessor、Gateway、KMS、Oracle/Relayer。
- [ ] 包含 1–10 的连续步骤编号。
- [ ] 每个步骤能看出发起方和接收方。
- [ ] 至少区分主交易线、密文计算线、解密返回线。
- [ ] 右侧包含步骤说明和关键解释。
- [ ] 没有严重交叉箭头导致流程不可读。

## Should

- [ ] 顶部有图例。
- [ ] HostChain / Coprocessor / Gateway 等大组件内部可显示核心子组件。
- [ ] 主流程优先于内部细节。
- [ ] 异步计算与解密流程视觉上能区分。

## Must Not

- [ ] 不得把 10 个步骤写成纯文字列表。
- [ ] 不得省略核心角色。
- [ ] 不得让箭头遮挡步骤编号或组件名称。
