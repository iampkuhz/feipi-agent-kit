# 既有治理结论待重审清单

说明：
- 本清单只记录待重审项，不在当前自检中顺手迁移其他 skills。
- 下列判断基于当前仓库可见目录、`CHANGELOG.md` 与 `feipi-skill-govern` 历史规则文本。

## 已落地但需重审的 rename 结论

1. `feipi-automate-dingtalk-webhook -> skills/integration/feipi-web-dingtalk-webhook/`
- 依据：`CHANGELOG.md` 于 2026-04-06 明确记录 action 从 `automate` 改为 `web`。
- 问题：该结论仍建立在旧 action-first 逻辑上，且 `web` 不是推荐 action。
- 处理：已在 2026-04-06 重审并落地为 `skills/integration/feipi-dingtalk-send-webhook/`，本条不再属于待执行迁移。

## 已迁移或已存在但需重审的 skill

- `skills/feipi-gen-innovation-disclosure`
- `skills/feipi-read-youtube-video`
- `skills/feipi-read-bilibili-video`
- `skills/feipi-summarize-video-url`

共同原因：
- 名称仍主要来自旧的 action-first 语法，或目录尚未完成 layer 归位。

## 应直接作废的未实施方案

- 所有基于旧 action-first 命名推导出的 Step 2C / Step 2D rename 方案。
- 所有把 `web`、`ops`、`automate` 当核心 action 的未实施迁移建议。
- 所有未经过新的 Step 1.5 模板复核的历史 rename plan。

## 可以保留的历史结论

- `authoring / diagram / integration / platform` 作为目录分层的思路可保留。
- 本地脚本优先、仓库级包装器从属的方向可保留。
- 版本与 changelog 的同日合并规则可保留。

## 建议的重启点

- 后续治理应从新的 Step 1 重新开始，而不是继续旧的 Step 2C / Step 2D。
- 第一批建议优先重审：
  - 仍平铺在 `skills/` 根下的 skills
