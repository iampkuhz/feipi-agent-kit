# 新增图类型标准流程

## 何时扩展

当用户需求无法被现有 typed profile（architecture / sequence / component / activity / deployment）覆盖时，按本流程新增图类型。

## 步骤

### 1. 确认图类型

- 确定 PlantUML 支持的未注册图类型（class / state / usecase 等）。
- 确认该类型的核心元素（如类图的 class/relationship，活动图的 node/transition）。

### 2. 创建 profile 文件

```
assets/templates/types/<type>-brief.yaml
assets/validation/types/<type>-brief.schema.json
assets/examples/<type>/<type>-brief.example.yaml
assets/examples/<type>/<type>-diagram.example.puml
```

### 3. 更新路由

- 在 `references/type-routing.md` 中添加关键词映射。
- 在 `references/diagram-type-profiles.md` 中注册新 profile。

### 4. 创建校验脚本

- 在 `assets/validation/types/<type>-brief.schema.json` 中新增 JSON Schema（由 `validate_package.sh` 通过 `lib/validate_brief_cli.py` 调用）
- `check_coverage.py` 中新增 `<type>` 覆盖逻辑。
- `lint_layout.sh` 中新增 `<type>` 布局规则。

### 5. 更新 SKILL.md

- 在"首批已迁移 profile"或"待迁移 profile"列表中添加新类型。

### 6. 验证

- 用 example brief 和 example diagram 跑通完整校验链。
- 确保 fallback mode 不受影响。
