# Skills 分层规则

## 目标

解决 skills 目录平铺导致的问题：
- 技能数量增长后难以导航
- 职责边界模糊，难以判断新技能应放在哪里
- 治理时无法按层批量处理

## 分层结构

```
skills/
├── authoring/          # 技能创作与治理
│   └── feipi-skill-govern/
├── diagram/            # 图表生成
│   ├── feipi-gen-plantuml-arch-diagram/
│   └── feipi-gen-plantuml-sequence-diagram/
├── integration/        # 外部服务集成
│   ├── feipi-read-youtube-video/
│   ├── feipi-read-bilibili-video/
│   ├── feipi-summarize-video-url/
│   └── feipi-automate-dingtalk-webhook/
└── platform/           # 平台/工具链集成
    └── feipi-ops-openclaw-config/
```

## 层定义

### authoring/

**职责**：用于创建、更新、重构、治理其他 skills 的技能。

**典型特征**：
- 输入是"某个 skill 的名称或目录"
- 输出是"重构后的 skill 结构或文档"
- 被治理的对象是 skills 本身

**现有技能**：
- `feipi-skill-govern`：Skill 工程治理总入口

**何时归入此层**：
- 当技能的主要职责是治理其他 skills 时

### diagram/

**职责**：生成可视化图表（PlantUML、流程图、时序图等）。

**典型特征**：
- 输入是"结构化描述或需求 brief"
- 输出是"可渲染的图表代码或图片"
- 核心能力是图表语法和布局

**现有技能**：
- `feipi-gen-plantuml-arch-diagram`：PlantUML 架构图生成
- `feipi-gen-plantuml-sequence-diagram`：PlantUML 时序图生成

**何时归入此层**：
- 当技能的主要输出是图表代码或可视化设计时

### integration/

**职责**：与外部服务/平台集成（视频平台、通讯工具、第三方 API）。

**典型特征**：
- 输入是"外部服务的 URL 或配置"
- 输出是"从外部服务提取的内容或操作结果"
- 需要处理认证、API 调用、数据下载

**现有技能**：
- `feipi-read-youtube-video`：YouTube 视频/音频下载与转写
- `feipi-read-bilibili-video`：Bilibili 视频/音频下载与转写
- `feipi-summarize-video-url`：视频 URL 摘要
- `feipi-automate-dingtalk-webhook`：钉钉机器人 webhook 发送

**何时归入此层**：
- 当技能需要调用外部服务 API 或处理外部平台数据时

### platform/

**职责**：与开发平台/工具链集成（代码托管、CI/CD、配置管理）。

**典型特征**：
- 输入是"平台配置或仓库设置"
- 输出是"平台配置文件或操作结果"
- 需要理解特定平台的配置格式和工作流

**现有技能**：
- `feipi-ops-openclaw-config`：OpenClaw 配置管理

**何时归入此层**：
- 当技能的主要职责是管理开发平台或工具链配置时

## 命名约束

每个 skill 的名称仍必须满足：
- `feipi-<action>-<target...>` 格式
- action 在标准字典中
- 总长度 <= 64 字符

**layer 不进入 skill 名称**，layer 只用于目录归类。

示例：
- `feipi-gen-plantuml-arch-diagram` 放在 `skills/diagram/` 下
- 名称不变，仍表达"生成 PlantUML 架构图"的职责
- layer 帮助导航，不负责命名

## 新建 skill 流程

1. **判定 layer**：根据上述层定义，确定技能应归属的层
2. **确定 skill 名**：按命名规范确定 `feipi-<action>-<target...>`
3. **选择目标路径**：`skills/<layer>/<skill-name>/`
4. **执行初始化**：使用 `feipi-skill-govern` 生成骨架

## 迁移已有 skill

若已有 skill 目录平铺在 `skills/` 下：
1. 使用 `feipi-skill-govern` 分析其职责
2. 判定应归属的 layer
3. 移动到 `skills/<layer>/<skill-name>/`
4. 更新引用和测试配置

## 为什么不按技术栈分层

- 技术栈（Python/JavaScript/Go）变化快，职责域相对稳定
- 用户找技能时，先想"要做什么"，而不是"用什么写"
- 治理时可以按层批量处理，如统一优化所有 `integration/` 下的认证逻辑

## 层的扩展与合并

- 新增层：当出现 3 个及以上技能共享同一职责域时，可新增层
- 合并层：当层下技能少于 2 个且职责接近其他层时，考虑合并
- 层名变更：需同步更新 `feipi-skill-govern` 和导航文档
