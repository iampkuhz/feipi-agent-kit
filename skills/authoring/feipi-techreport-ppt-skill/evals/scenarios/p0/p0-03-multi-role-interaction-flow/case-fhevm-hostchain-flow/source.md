# Source: Zama FHEVM 架构与交互流程

请基于以下材料生成 1 页 16:9 中文技术汇报 PPT。材料已经足够，不需要外部调研，也不要补充未提供的事实。

## 页面基本信息

- 标题：Zama FHEVM 架构与交互流程
- 副标题：用户直接与 HostChain 合约交互
- 受众：CTO、技术负责人、隐私计算 / 区块链研发团队
- 页面类型：多角色交互流程 / 泳道流程页

## 页面目标与结论

这一页要用多角色交互流程图解释用户 / DApp、HostChain、Coprocessor、Zama Gateway、KMS、Oracle / Relayer 之间的核心交互关系。

希望 CTO 看完记住的结论是：用户业务交易直接进入 HostChain 合约，密文计算在 Coprocessor 网络异步完成，Gateway 负责结果承诺聚合和 ACL 检查，KMS 只在需要 reveal / read 明文时参与阈值解密，Oracle / Relayer 负责回写链上或返回用户。

## 角色 / 组件

流程图至少包含 6 个角色或泳道：

1. 用户 / DApp
2. HostChain（以太坊 / L2）
3. Coprocessor 网络
4. Zama Gateway
5. KMS 网络
6. Oracle / Relayer

可在大组件内部展示少量子组件，但主流程优先于内部细节。

## 10 个必须编号的步骤

请按 1-10 连续编号展示步骤，每个步骤要能看出发起方和接收方。

1. 用户在本地选择明文业务数据并生成加密输入。
   - 发起方：用户 / DApp
   - 接收方：用户 / DApp 本地
   - 类型：本地处理

2. SDK 输出 encrypted handles 与 inputProof。
   - 发起方：用户 / DApp
   - 接收方：用户 / DApp 本地
   - 类型：本地处理

3. 用户钱包直接调用 HostChain 业务合约。
   - 发起方：用户 / DApp
   - 接收方：HostChain
   - 类型：主交易线

4. 合约 / Executor 发出符号化 FHE 计算事件。
   - 发起方：HostChain
   - 接收方：Coprocessor 网络
   - 类型：输入 / 密文计算线

5. Coprocessor 在密文上执行 FHE 计算。
   - 发起方：Coprocessor 网络
   - 接收方：Coprocessor 网络
   - 类型：输入 / 密文计算线

6. Coprocessor 将结果承诺与签名提交 Gateway 聚合。
   - 发起方：Coprocessor 网络
   - 接收方：Zama Gateway
   - 类型：内部 / 状态同步线

7. 用户发起解密请求。
   - 发起方：用户 / DApp
   - 接收方：Zama Gateway
   - 类型：解密请求线

8. Gateway 检查 ACL 并调用 KMS。
   - 发起方：Zama Gateway
   - 接收方：KMS 网络
   - 类型：解密请求线

9. KMS 阈值解密并输出签名结果。
   - 发起方：KMS 网络
   - 接收方：Oracle / Relayer
   - 类型：解密返回线

10. Oracle / Relayer 回写链上或返回用户。
    - 发起方：Oracle / Relayer
    - 接收方：HostChain 或用户 / DApp
    - 类型：解密返回线

## 线型 / 图例

请至少区分 4 类线：

- 主交易线：用户钱包直接调用 HostChain 业务合约。
- 输入 / 密文计算线：HostChain 事件触发 Coprocessor 密文计算。
- 解密请求线：用户请求 Gateway，Gateway 调用 KMS。
- 解密返回线：KMS 输出签名结果，Oracle / Relayer 回写链上或返回用户。
- 内部 / 状态同步线：Coprocessor 将结果承诺与签名交给 Gateway 聚合。

## 右侧步骤说明和关键解释

右侧需要有步骤说明和关键解释，内容短句化：

- 第 3 步是业务交易：用户直接打到 HostChain 合约。
- 第 4-6 步是异步密文计算与结果承诺，不产生明文。
- 第 6 步把结果承诺交给 Gateway，用于多数共识、审计和 slashing。
- 第 7-10 步仅在需要 reveal / read 明文时触发。

## 版式与生成要求

- 主流程图区占页面主体，右侧说明区不要抢占主流程。
- 步骤编号要醒目，不能被箭头遮挡。
- 箭头方向必须能表达时序，避免严重交叉。
- 不要把 10 个步骤做成纯文字列表，必须有多角色流程图。
- 顶部可放图例，帮助区分主交易线、密文计算线、解密请求线、解密返回线、内部同步线。
- 整页风格应正式、工程化、克制，适合 CTO 技术汇报。
