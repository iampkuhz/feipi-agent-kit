# Skills 分层规则

## 核心原则

- layer 只负责目录分层与治理导航，不进入 skill 主名称语法。
- 命名决策顺序固定为 `domain -> action -> object -> layer`。
- 不为单个 skill 临时发明 layer；新增 layer 必须能覆盖一组稳定的 skill 类型，而不是一次性安置问题。
- layer 不能替代 domain；名称表达职责，layer 表达目录归位。

## 当前允许的 layer

### `authoring/`

- 职责：结构化文稿产物与治理产物的创作、重构、自检，包括 skill 本身以及模板驱动的提案、报告、交底书等文稿。
- 适用：核心输出是结构化文稿、治理材料或规范文本，而不是远程集成、图表代码或平台配置。

### `diagram/`

- 职责：图表、图形描述、渲染输入物的生成。
- 适用：核心产物是图表代码、结构图、时序图等可视化结果。

### `integration/`

- 职责：外部平台、服务、内容源或消息通道的接入。
- 适用：核心动作需要访问第三方平台、下载内容、发送 webhook、调用远程接口。

### `platform/`

- 职责：开发平台、运行平台、工具链或配置系统的管理。
- 适用：核心动作是配置、管理、生成平台相关设置或运行参数。

## 判定方法

1. 先按命名规范确定 `target_domain`、`target_action`、`target_object`。
2. 再根据 skill 的主要职责选择 `target_layer`。
3. 最终目录使用 `skills/<layer>/<skill-name>/`。

## 常见误区

### 把 layer 写进 skill 名

反例：
- `feipi-integration-read-youtube`
- `feipi-platform-configure-openclaw`

问题：
- layer 与名称重复表达，导致名称变长但语义没有更清楚。

### 用 layer 兜底命名不清

反例：
- “先放到 integration，再随便起名为 `feipi-web-dingtalk-webhook`”

问题：
- `integration/` 只能说明目录归属，不能替代 action 的语义质量。

### 为单个 skill 临时发明 layer

反例：
- 仅因为一个 skill 特殊，就新增 `skills/video/`、`skills/ops/`。

问题：
- 目录层级会变成历史包袱，治理成本高于收益。

## 新增或调整 layer 的门槛

- 需要至少 3 个以上 skill 会稳定使用该 layer。
- 需要能清楚区分与现有 layer 的边界。
- 需要先更新 `feipi-skill-govern` 的规则、模板、脚本与导航，再允许落地。

## 可保留的内容

- `authoring/`、`diagram/`、`integration/`、`platform/` 的分层思想可继续保留。
- 历史 skill 若名称仍是旧规则，可先记录到待重审清单；layer 本身不必因此废弃。
