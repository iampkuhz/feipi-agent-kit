# 候选界面审阅与确认

用户要求手工逐份审阅时，候选先存于隔离工作区。每份 Skill 完成即可生成一份本地 HTML 快照，其他草稿可以继续准备。批准后才进入正式安装范围。若调用者依赖仍待批准的 Skill，先保留候选，等依赖具备后再发布。

## 审阅者应看到什么

- 准确 ID、Description、完整的渲染和原始 `SKILL.md`、实际文件清单和内容。新增说明写清每份 Reference 的用途。更新既有 Skill 时展示文本差异。
- 哪些 Skill 相邻、触发条件如何区分、谁调用目标 Skill、传入什么以及期待什么结果。
- 项目 Reference、宿主和插件依赖、已验证的行为及限制。涉及路径时展示实际解析根、换位置后的验证和受阻项。缺失驱动、隔离演练和真实平台运行按其实际范围标注。

涉及直接共享文件时，将这些文件的文本差异填入 `shared_diff`，并在 `shared_files` 登记仓库相对路径到实际文件 SHA-256 的映射。生成和确认时都加 `--workspace "$source_root"`，共同核对共享变更。把上述面向审阅者的说明填进 [审阅资料模板](../templates/review-context.template.json)。使用 `uv` 运行生成器。首次准备 Markdown 渲染依赖时需要依赖缓存或网络。网页产物可离线打开。

```sh
uv run scripts/review_skill.py "$candidate" --baseline "$baseline" --context "$context" --out "$review_dir"
```

新建 Skill 省略 `--baseline`。用户可用候选页核对内容。只能用手机审阅时，在 Codex 聊天中先展示本次实际改动、验证及版本，再按需贴同一快照的原文与差异。用户可在当前对话中按文件反馈或确认这份候选。人工确认记录的字段为 `skill`、`status`（`approved`）、`fingerprint` 和 `evidence`（实际确认出处）。确认前不存在通过记录，工具不会代替审阅者填写。

```sh
python3 scripts/review_skill.py "$candidate" --context "$context" --check-approval "$approval_file"
```

检查把确认绑定到实际候选文件和审阅资料的摘要。文件增删、运行资源变化或审阅资料更新都需要核对新版本。校验器只核对记录存在及摘要匹配，人工确认的真实性仍须从对应出处核实。审批快照和报告留在本轮工作目录，避免一起安装。未批准的候选在隔离目录准备，避免现行安装器的链接提前带入修改。
