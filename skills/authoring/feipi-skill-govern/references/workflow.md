# 工作流与执行边界

## 总原则

- 先规则后实现：先锁定真规则和边界，再修改文件。
- 目标收敛：默认只治理一个目标 skill。
- 治理优先：先修命名、触发、执行、脚本归位、验证闭环，再做纯文案整理。
- 验证优先：没有结构校验、行为校验和旧规则残留搜索，就不算完成。

## 执行顺序

1. Scope
- 判断任务是否真的是 skill 治理任务。
- 锁定 `target_skill`、`task_type`、`allowed_shared_files`。
- 若用户没有点名多 skill，不扩散到其他 skills。

2. Step 1 基线审计
- 读取 `SKILL.md`、`agents/openai.yaml`、直接使用到的 `references/`、`scripts/`、`assets/`、`templates/`。
- 输出问题清单，标记命名、layer、触发、执行、资源、脚本归位、验证状态。

3. Step 1.5 命名与归位评审
- 仅在命名、路径、layer 有争议时进入此步。
- 严格按 `domain -> action -> object -> layer` 决策。
- 若旧 rename 结论来自 action-first 规则，只能记录为待重审，不能直接沿用。

4. Step 2 定点修复
- 先改最影响结果稳定性的文件。
- 触发问题：优先改 frontmatter、`agents/openai.yaml`。
- 执行问题：优先改 `SKILL.md`、直接关联的 `references/`。
- 资源和脚本问题：优先改本地 `scripts/`、`assets/`、`templates/`，不要继续把仓库级包装器当核心依赖。

5. Step 3 验证与收口
- 结构校验：`bash scripts/validate.sh <skill-dir>`。
- 行为校验：`bash scripts/test.sh` 或更贴近目标 skill 的本地 test。
- 旧规则残留搜索：搜索旧命名文本、过时模板占位符、旧入口依赖。
- 版本与记录：按 `references/version-policy.md` 与 `references/changelog-policy.md` 收口。

## 文件与问题映射

- 命名 / layer 问题：
  改 `references/naming-conventions.md`、`references/skill-layering-policy.md`、相关脚本校验逻辑。
- 误触发 / 漏触发：
  改 frontmatter 与 `agents/openai.yaml`。
- 执行边界不清：
  改 `SKILL.md` 与 `references/governance-process.md`。
- 模板漂移：
  改 `templates/` 与 `assets/governance/`。
- 本地闭环不足：
  改 `scripts/init_skill*.sh`、`scripts/validate.sh`、`scripts/test.sh`。

## 共享文件边界

- 默认只允许修改目标 skill 自身文件。
- 仅当模板、脚本或共享规则与目标 skill 直接绑定时，才允许连带修改对应共享文件。
- README、CHANGELOG 只有在入口、命令、版本或治理说明直接变化时才同步。
- 发现其他 skill 的问题时，记录到待重审清单，不顺手改名或迁移。

## 失败处理

- 目标不清：默认收敛到用户明确点名的 skill。
- 与无关改动冲突：先停下来缩小影响面，不回滚别人的改动。
- 无法验证：写清阻塞点、未覆盖环节和风险。
- 历史流程已失真：暂停后续 Step 2x，回到 Step 1 重新建基线。

## 命令边界

### 仓库根目录执行

```bash
bash skills/authoring/feipi-skill-govern/scripts/validate.sh skills/authoring/feipi-skill-govern
bash skills/authoring/feipi-skill-govern/scripts/init_skill.sh feipi-video-read-youtube --layer integration
```

### 当前 skill 目录执行

```bash
bash scripts/validate.sh .
bash scripts/test.sh
```

说明：
- `scripts/validate.sh` 是主结构校验入口。
- `scripts/test.sh` 是主行为校验入口。
- 仓库级 `make` 只能包装本地脚本，不可替代本地入口。

## 最低验证矩阵

- 结构校验：目录位置、命名结构、frontmatter、`agents/openai.yaml`、脚本存在性。
- 行为校验：至少覆盖一条真实动作链，例如初始化临时 skill 或运行目标 skill 的本地测试。
- dry-run / 非破坏性验证：优先使用临时目录、只读搜索、占位符扫描。
- 旧引用残留搜索：检查旧命名文本、旧 action-first 规则、旧 make 依赖是否残留在规范文件和模板中。
