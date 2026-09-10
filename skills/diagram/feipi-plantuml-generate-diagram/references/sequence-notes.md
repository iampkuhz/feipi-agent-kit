# 时序图 note 排版

适用于 `sequence` 的 `interaction_mr` 和 `process_s`，包括用时序图表达的业务流程；不套用到 activity 图的 note 语法。

## 写法与决策

消息说明紧跟对应箭头，使用多行 `note right` / `note left`，正文用真实换行，最后 `end note`。不要用 `note right of XX` / `note left of XX` 表达消息说明，避免额外占据纵向空间。参与者职责、初始状态等独立说明仍可用 `of` / `over`，不要机械改成上一条消息的注释。

```plantuml
caller -> service : M1 提交请求
note right
校验请求参数
保留原始业务编号
end note
```

1. 按画面位置找出当前箭头两端中较左和较右的参与者；返回箭头也遵循此规则，不按发送方/接收方判断左右。
2. 比较左端到左边界、右端到右边界的剩余宽度，扣除 note 留白后选较宽的一侧；同宽固定选右侧。越靠近所选边界，单行可容纳的文字越少。
3. 按该宽度折行，另算跨全体参与者时的行数。仅当侧边 **至少 4 行** 且全宽 **至少少 3 行** 时，改成紧跟当前消息的 `note across ... end note`，占据下方一行。不要只因达到 4 行就改全宽。
4. 两侧均不足以容纳一个中文字符时，直接全宽；全宽也不足则报错并调整参与者间距。普通长 note 不得通过任意增加图宽逃避行数比较。
5. 优先保留内容、语义段落和英文单词；超长单词才拆分。已有为排版插入的硬换行应先还原，真正的列表或段落换行保留。

语法依据：[官方时序图文档的 Notes on messages 与 Note over all participants](https://plantuml.com/sequence-diagram)。

## 批量计算

note 与时序图原始需求一起输入，直接写在 `messages[].note` 中；不要另建 note 清单或重复填写参与者、编号、from/to。Agent 整理自然语言需求时，也应将消息说明放入同一份 brief。没有说明的消息省略 `note`，旧 brief 无需补空字段。

下面是完整 brief 中的消息片段；其他必填字段沿用原时序图模板：

```yaml
messages:
  - id: M1
    from: user
    to: web_portal
    description: 提交下单请求
    type: sync
    note: 校验商品与数量，保留客户端请求编号用于重复提交检查。
```

在 skill 目录执行，直接读取原始 brief：

```bash
# 单图
python3 scripts/plan_sequence_notes.py --brief sequence-brief.yaml

# 多图批量；输出包含每份原始 brief 的路径，允许各文件复用 D1 等编号。
python3 scripts/plan_sequence_notes.py \
  --brief assets/examples/sequence/sequence-brief.example.yaml \
          assets/examples/sequence/sequence-process-s-brief.example.yaml \
  --output /tmp/sequence-note-plan.json
```

脚本复用原有 schema 和语义校验，自动提取参与者顺序与各消息中的 note。把结果中的 `puml` 紧贴到对应消息后（放在 activate、deactivate、分隔线或下一条消息之前），再走原有图包验证。输出 JSON 是中间计算结果，不是用户需要再维护的一份需求；脚本不会解析或覆盖原始 `.puml`。

- `participants` 必须与图中从左到右的实际顺序一致，2–8 个；复用消息的 `from/to`，也支持自调用。每条消息最多一个 `note` 字符串，多段说明用 YAML `|` 保留换行。
- `note` 支持中英文纯文本、标点、实际换行和字面量 `\n`；不自动处理 Creole/HTML、图片、控制字符或预处理内容。富文本不进入计算器，需另行人工排版。
- 无坐标时按等距参与者估算（间隔 24 显示列、两端各 12 列），输出 `geometry_source: estimated`。这些值是排版启发式，不是 renderer 的默认值；长消息、不等距参与者、激活条和自调用回环可能需要实际空间。
- 已有布局时，在同一 brief 的 `layout.note_geometry` 下可选填写 `left`、`right` 和各参与者的 `x`。必须完整提供坐标且按声明顺序严格递增，输出 `geometry_source: provided`。普通需求无需填写。

```yaml
layout:
  direction: top_to_bottom
  include_legend: false
  note_geometry:  # 可选的排版信息，通常由 Agent 根据已有布局填写
    left: 0
    right: 120
    x: {user: 12, api: 48, db: 108}
```

- 坐标及宽度统一用**显示列**，中文/全角通常占 2，ASCII 占 1。若从 SVG 取得像素，先用相同字体下一个 ASCII 字符的参考像素宽度归一化所有横坐标和边界，不可混用像素。边界是计划保留的正文边界，不应包含标题/图例额外撑开的画布宽度。
- 留白和阈值统一由 `scripts/lib/sequence_notes.py` 常量维护。左右可用宽度分别为 `floor(min(x1,x2) - left - padding)`、`floor(right - max(x1,x2) - padding)`；全宽保守取首末生命线距离减 padding。
- 输出每条 note 的左右/全宽预算、两种行数、方向、决策原因、折行正文和 `puml`；错误标明 brief 路径，整批校验通过才输出。无 note 的图返回空 note 列表。

## 验证边界

计算器不调用 renderer，也不声称求得全局最佳排版；字体、比例、消息宽度和 note 本身都会影响实际几何。即使提供坐标，行宽仍是估算。输出固定 `visual_review: pending`。

将片段放入图后，沿用唯一的 `validate_package.sh` 真实图包校验，复核：左右是否符合可用空间、是否遮挡消息/生命线、是否拉宽画布、全宽是否明显减少纵向空白、中文和换行是否完整。不得新增反复渲染的自动调优循环。渲染或视觉复核未完成时明确报告，不把计算成功当作图包成功。
