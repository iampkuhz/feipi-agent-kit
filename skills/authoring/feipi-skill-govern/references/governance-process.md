# Skill 治理流程（第二阶段复用指南）

## 目标

本文档说明如何使用 `feipi-skill-govern` 去治理其他 skills。
适用场景：
- 批量优化已有 skills 的结构
- 迁移共享脚本到 skill 本地
- 修复命名、分层、文档问题
- 为每个 skill 建立独立运行能力

## 治理范围

本流程适用于：
- 已存在但结构不规范的 skills
- 需要迁移到当前仓库的 skills
- 需要统一规范和验证闭环的 skills

## 治理原则

1. **先分析后修改**：先用 `validate.sh` 校验，输出问题清单
2. **先本地后全局**：优先将共享脚本/模板迁移到 skill 本地
3. **先功能后美化**：优先修复影响触发和执行的问题，再处理文档美化
4. **先单点后批量**：先治理一个 skill 作为范式，再批量复制流程
5. **有验证才交付**：每个治理步骤后必须执行验证

## 治理步骤

### 步骤 1：分析目标 skill

```bash
# 1. 读取目标 skill 的当前结构
ls -la <skill-dir>/

# 2. 执行校验，输出问题清单
bash scripts/validate.sh <skill-dir>

# 3. 记录当前问题类型
- [ ] 共享依赖问题（依赖 feipi-scripts/ 或 templates/）
- [ ] 目录分层问题（平铺在 skills/ 下）
- [ ] 入口混乱问题（make 和本地脚本并存）
- [ ] 文档边界问题（description 不清晰）
- [ ] 验证缺失问题（缺少 test.sh 或验证太弱）
```

### 步骤 2：设计治理方案

根据问题类型设计方案：

| 问题类型 | 治理方案 |
|----------|----------|
| 共享依赖 | 迁移 `feipi-scripts/` 和 `templates/` 到 skill 本地 |
| 目录分层 | 移动到 `skills/<layer>/<skill-name>/` |
| 入口混乱 | 明确本地脚本是标准入口，`make` 只是包装器 |
| 文档边界 | 更新 `description` 和 `SKILL.md` 明确职责 |
| 验证缺失 | 新增或强化 `scripts/test.sh` |

### 步骤 3：迁移共享脚本

若目标 skill 依赖仓库级共享脚本：

```bash
# 1. 复制共享脚本到 skill 本地
cp feipi-scripts/repo/init_skill.sh <skill-dir>/scripts/init_skill_internal.sh
cp feipi-scripts/repo/quick_validate.sh <skill-dir>/scripts/quick_validate_internal.sh
cp templates/*.template.* <skill-dir>/templates/

# 2. 修改内部脚本路径指向 skill 本地 templates/
# 3. 创建 wrapper 脚本转发到内部脚本
# 4. 验证迁移后脚本可独立运行
bash <skill-dir>/scripts/validate.sh <skill-dir>
```

### 步骤 4：更新 SKILL.md

更新目标 skill 的 `SKILL.md`：

1. 更新 frontmatter 的 `description`，明确职责和触发时机
2. 更新命令入口，优先使用本地脚本
3. 若有"维护与回归"章节，确认是否应下沉到开发流程文档
4. 更新引用的 `references/` 路径（若迁移了 shared 脚本）

### 步骤 5：更新 agents/openai.yaml

确保 `agents/openai.yaml` 包含：
- 顶层整数 `version`
- `interface.display_name`（中文）
- `interface.short_description`（中文，<=100 字）
- `interface.default_prompt`（中文，覆盖决策顺序和验证要求）

### 步骤 6：执行验证

```bash
# 1. 结构校验
bash scripts/validate.sh <skill-dir>

# 2. 执行测试
bash <skill-dir>/scripts/test.sh

# 3. 若有问题，修复后重新验证
```

### 步骤 7：更新版本和 changelog

若治理过程中修改了目标 skill：

1. 检查 `agents/openai.yaml` 的 `version`
2. 若当天首次修改，递增 version
3. 更新仓库根目录 `CHANGELOG.md`，在当天日期下记录

## 治理检查清单

治理完成后，确认以下项目全部打勾：

```txt
结构检查
- [ ] skill 目录在正确的 layer 下（如 skills/authoring/feipi-skill-govern/）
- [ ] 目录名符合 feipi-<action>-<target...> 格式
- [ ] 存在 SKILL.md、agents/openai.yaml、scripts/test.sh

独立性检查
- [ ] scripts/ 包含 init、validate、test，不依赖仓库级脚本
- [ ] templates/ 包含所需模板（若有初始化能力）
- [ ] 脱离仓库级 Makefile 也能独立运行

文档检查
- [ ] frontmatter 的 description 清晰表达职责
- [ ] SKILL.md 的命令入口使用本地脚本
- [ ] references/ 路径正确且文件存在

验证检查
- [ ] bash scripts/validate.sh 通过
- [ ] bash scripts/test.sh 通过
- [ ] 生成临时 skill 验证初始化流程

版本检查
- [ ] agents/openai.yaml 有顶层 version 字段
- [ ] version 符合当日规则（首次修改升版）
- [ ] CHANGELOG.md 有对应记录
```

## 批量治理流程

当需要治理多个 skills 时：

1. **选范式**：先选一个 skill 作为范式，完成完整治理流程
2. **沉淀脚本**：将治理步骤脚本化为 `scripts/migrate.sh` 或类似工具
3. **批量执行**：对每个 skill 执行相同流程
4. **统一验证**：对所有治理后的 skill 执行验证

## 常见陷阱

| 陷阱 | 症状 | 修复 |
|------|------|------|
| 只改目录不改依赖 | 移动了 skill 但脚本仍指向仓库根 | 同步更新脚本中的路径计算逻辑 |
| 只改文档不改验证 | SKILL.md 改了但 test.sh 仍用旧入口 | 同步更新 test.sh 和验证脚本 |
| 只改技能不改自身 | 治理了其他 skill 但 feipi-skill-govern 自己没同步 | 若治理流程依赖 feipi-skill-govern 自身能力，需自举验证 |
| 批量修改变失真 | 批量治理后每个 skill 看起来一样但行为不对 | 每个 skill 治理后必须单独验证行为正确性 |

## 回滚策略

若治理后出现问题：

1. 使用 git 回滚到治理前状态
2. 分析问题根因（路径？权限？依赖？）
3. 在本地环境复现并修复
4. 重新执行治理流程

## 第二阶段交付物

第二阶段结束后应交付：
1. 所有治理后的 skills 位于正确的 layer 下
2. 每个 skill 可独立运行，不依赖仓库级共享脚本
3. `feipi-skill-govern` 可作为治理范式样板
4. 本治理流程文档已验证可用
