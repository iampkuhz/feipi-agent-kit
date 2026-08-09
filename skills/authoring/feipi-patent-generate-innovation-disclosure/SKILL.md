---
name: feipi-patent-generate-innovation-disclosure
description: 用于把零散业务与技术事实整理为带来源台账、PlantUML 图包和内容质量门禁的专利创新交底包；在需要专利交底初稿或评审材料时使用。若只需单图、创意润色、法律意见或 skill 治理，不要使用。
---

# 专利创新交底包生成

## 目标与边界

生成可评审的交付包，而不是只生成一篇格式完整的 Markdown。交付包必须让来源、创新主张、技术效果、图文编号和复核状态相互可追溯。

不要把本地校验结果表述为专利新颖性、法律可专利性或外部资料真实性证明。没有可靠竞品证据时标记“待检索”，不要补写未经证实的产品能力。

## 成稿前门槛

先从对话和用户材料提取已知信息，只追问缺失项。进入成稿前必须具备：

- 专利名和使用场景。
- 至少 1 个技术对象。
- 至少 1 个核心机制。
- 至少 1 个必要约束或边界。
- 至少 1 个现有问题事实。

缺少任一项时定向追问并暂停成稿。不得用推测出的“发明扩展”冒充来源事实。

开始工作时读取：

- `references/content-quality-gates.md`：十类内容规则、正反例和验证边界。
- `assets/proposal_template.md`：正式文档结构。
- `assets/disclosure-manifest.template.json`：manifest 字段模板。
- `assets/disclosure-manifest.schema.json`：manifest 结构合同。

## 交付包合同

默认输出以下目录；`disclosure-manifest.json` 是内容真源：

```text
<package>/
├── disclosure.md
├── disclosure-manifest.json
├── disclosure-validation.json
└── diagrams/
    └── <D编号>-<用途>/
        ├── brief.normalized.yaml
        ├── diagram.puml
        ├── diagram.svg
        └── validation.json
```

只使用包内相对路径；禁止绝对路径和 `..`。每个 Markdown PlantUML 块前写稳定标识：

```markdown
<!-- diagram-id: D1 -->
```

`disclosure-validation.json` 的最终状态只有三种：

- `success`：确定性检查和必做复核均通过；可保留诚实警告。
- `review_required`：机器检查通过，但语义或视觉复核仍为 `pending`。
- `blocked`：确定性规则失败，或任一必做复核为 `fail`。

## 执行流程

1. **建立事实台账**
   - 将输入分为“来源事实 / 发明扩展 / 外部资料”。
   - 为发明扩展记录依据事实；为外部资料记录定位地址、检索日期和证据属性。
   - 将类名、函数、字段、表名和内部产品名泛化为技术表达；必要缩写加入白名单。

2. **确定边界与主张**
   - 先确定业务域、系统归属、拥有方、物理边界和部署触发条件，再拆组件。
   - 先写唯一的核心发明主张，再提炼 2–4 个 `I1...In` 创新点。
   - 每个创新点写全核心机制、必要约束、实质差异和正文/图示落点。

3. **建立效果映射**
   - 为每个创新点建立唯一的 `T1...Tn` 技术效果，保持一一映射。
   - 每项写全原问题、采用机制、可观察结果和验证状态。
   - `verified` 必须通过 `evidence_source_ids` 绑定已有 `SF/EM`；没有实测数据时使用 `expected_observable`。

4. **规划并生成图示**
   - 统一调用 `$feipi-plantuml-generate-diagram`，先生成 brief，再验证图包，最后嵌入文档。
   - 必须且只能有 1 张 `component_overview` 和 1 张 `main_flow`。
   - 主流程由分支/状态驱动时使用 `activity`；由多方调用/回执驱动时使用 `sequence` 且设置 `numbering_scheme: process_s`。
   - 出现跨网、跨链、在线/离线、HSM、人工摆渡或人工交接时，增加 `deployment_boundary`。
   - `module_detail` 每张只展开一个父组件；`core_mechanism` 仅在有独立目的时生成，不为凑图添加。
   - 图示使用 `D1...Dn`；结构关系使用 `E1...En`；流程使用 `S1...Sn`、`S5.1...`。专利文档不得出现 `M/R` 编号。

5. **按模板写作**
   - 标题、使用场景、核心发明主张、关键词及 `I/T` 字段从 manifest 原样渲染，补充解释写在原字段之后。
   - 关键词固定为 5–8 个：技术对象 1–2、核心机制 2–4、关键约束 1–2，三组互斥。
   - 顶层组件只放业务域、独立系统和物理端点；实现类、函数、JAR、处理器和表字段只能作为细节。
   - 主流程顶层保持连续 5–10 步；箭头标签只保留编号或一个动作短语，参数和异常处理写在图下。
   - 竞品部分只写证据完整的 1–3 项；没有可靠证据时明确写“待检索”。

6. **完成语义与视觉复核**
   - 执行泛化替换测试：替换领域名词后仍适用于任意系统的内容判为失败。
   - 逐项执行因果删除测试：删除核心机制后技术效果仍成立的映射判为失败。
   - 复核 SVG 是否零交叉、零文字遮挡；复核结果绑定当前 `svg_sha256`，图变化后重新复核。
   - 机器脚本只验证复核记录及其绑定关系，不声称自动理解语义或视觉质量。

7. **验证并交付**
   - 先校验各 diagram package，再校验完整交底包；完整入口会再次调用通用图包 v1.1 verifier 重算路径、状态、hash 与实际 metrics。
   - 修复 `blocked` 规则后重跑；`review_required` 必须完成相应人工复核后再交付为 `success`。
   - 保留验证报告中的警告和验证边界，不把“待检索”改写成伪证据。

## 校验入口

兼容旧调用，仅检查单篇草稿并提示缺少完整交付包：

```bash
bash scripts/check_disclosure_format.sh <document.md>
```

完整交付的唯一主入口：

```bash
bash scripts/validate_disclosure_package.sh <package-dir>
```

## 失败处理

- 输入不足：列出缺失字段并定向追问，不生成占位成稿。
- 来源悬空：删除断言、补来源，或明确标记待检索；不要猜测。
- 图包失败：先修 diagram package，不把未通过的 PlantUML 贴入正文。
- 语义或视觉复核待完成：输出 `review_required`，不得宣称全部通过。
- 校验规则与模板冲突：以 schema 和 `references/content-quality-gates.md` 为内容合同，记录冲突并修复同源资源。

## 资源导航

- 内容质量规则：`references/content-quality-gates.md`
- 正式文档模板：`assets/proposal_template.md`
- manifest 模板与 schema：`assets/disclosure-manifest.template.json`、`assets/disclosure-manifest.schema.json`
- 草稿兼容样例：`references/cases/happy-case-full.md`
- 完整合成交付包：`references/cases/happy-package/`
