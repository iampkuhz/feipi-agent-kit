# Skill installation manifests

这里不保存 skill 源码。每个 `*.json` 独立声明一个 skill 的 Git 来源和安装配置，`make bootstrap` 根据这些文件把对应子目录同步到固定的 `~/.openclaw/skills/<name>`。

最小格式：

```json
{
  "version": 1,
  "name": "example-skill",
  "homepage": "https://github.com/owner/repo/tree/main/path/to/example-skill",
  "source": {
    "type": "git-subdirectory",
    "repository": "https://github.com/owner/repo.git",
    "ref": "main",
    "path": "path/to/example-skill"
  }
}
```

安装包排除 skill 根目录下的 `tests/`、`evals/`；开发验证留在 Git 来源中，运行入口只安装指令、脚本和所需资源。

可选配置：

- `enabled: false`：暂不参与默认安装；必须同时写明 `disabledReason`。
- `setup.npmInstall: true`：安装或更新后在 managed skill 目录执行 `npm ci --omit=dev --ignore-scripts`。
- `runtime.requiredEnv`：记录运行时需要的环境变量；bootstrap 只报告缺失，不读取或打印变量值。

一次同步全部 manifest：

```bash
make bootstrap
```

只同步一个：

```bash
make bootstrap SKILL=skill-list/feipi-video-read-url.json
```

删除 manifest 不会自动删除已安装 skill；卸载属于独立的显式操作，避免清单误删导致 live 状态被破坏。

`feipi-growth-record-diary` 使用本机独立资料库的 Git 来源 `/Users/zhehan/Documents/life/child-growth-diary`，不需要发布孩子资料。迁移或从零部署时，先恢复该目录的源码分支；日记与媒体由独立备份恢复，Git 不包含它们。

本地 Git 来源可显式设置 `setup.useLocalWorkingTree: true`，要求当前分支与 ref 一致，并记录运行源码树 SHA-256；安装不触发 Git 提交。未启用该选项的来源仍按 Git ref 克隆。

`feipi-housing-capture-inbox` 的来源指向本机独立住宅装修 Git 仓库，使用 `main` 工作树与来源哈希安装。迁移时先恢复 `/Users/zhehan/Documents/life/2028.装修/home-renovation-playbook-2028` 的源码与 Git 历史，再执行 bootstrap；日记和附件单独恢复。安装仅取 `.agents/skills/feipi-housing-capture-inbox`，不读取日记与媒体。

`feipi-video-read-url` 与 `feipi-xiaohongshu-read-note` 使用本机 `/Users/zhehan/Documents/tools/llm/feipi-agent-kit` 的 `main` 工作树，安装器记录已提交基线及运行源码树哈希；迁移时先恢复该源码仓库。修改仅在来源维护，再按 manifest 安装，不直接修改受管 skill。
