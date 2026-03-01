# 本仓库的常用命令入口：
# - `make new`：初始化 skill 骨架
# - `make validate`：校验单个 skill 目录
# - `make list`：列出已有 skills
# - `make install-links`：将本仓库 skills 软链接到用户目录
# - `make test`：按统一入口执行 skill 测试
SHELL := /bin/bash
SKILL ?=
RESOURCES ?=
TARGET ?=
DIR ?=

.PHONY: new validate list install-links test

# 创建新 skill（默认优先 `skills/`，可切换到 `.agents/skills`）。
# 示例：make new SKILL=gen-api-tests RESOURCES=scripts,references
# 示例：make new SKILL=gen-api-tests TARGET=repo
new:
	@if [[ -z "$(SKILL)" ]]; then echo "用法: make new SKILL=<name> [RESOURCES=scripts,references,assets] [TARGET=auto|skills|repo|<path>]"; exit 1; fi
	./feipi-scripts/repo/init_skill.sh "$(SKILL)" $(if $(RESOURCES),--resources "$(RESOURCES)") $(if $(TARGET),--target "$(TARGET)")

# 校验一个 skill 目录。
# 示例：make validate DIR=skills/feipi-gen-skills
# 示例：make validate DIR=.agents/skills/feipi-gen-skills
validate:
	@if [[ -z "$(DIR)" ]]; then echo "用法: make validate DIR=<skill-dir>/<name>"; exit 1; fi
	./feipi-scripts/repo/quick_validate.sh "$(DIR)"

# 列出 `skills/` 与 `.agents/skills/` 下一层目录。
list:
	@{ \
		if [[ -d skills ]]; then find skills -maxdepth 1 -mindepth 1 -type d; fi; \
		if [[ -d .agents/skills ]]; then find .agents/skills -maxdepth 1 -mindepth 1 -type d; fi; \
	} | sort

# 将仓库 `skills/` 下各 skill 软链接到目标目录（默认 ~/.agents/skills）。
# 示例：
# - make install-links
# - AGENT=qwen make install-links
# - AGENT=qoder make install-links
# - AGENT=openclaw make install-links
install-links:
	./feipi-scripts/repo/install_skills_links.sh

# 统一执行 skill 测试入口。
# 示例：
# - make test SKILL=feipi-read-youtube-video
# - make test SKILL=read-youtube-video
test:
	@if [[ -z "$(SKILL)" ]]; then echo "用法: make test SKILL=<name>"; exit 1; fi
	./feipi-scripts/repo/run_skill_test.sh "$(SKILL)"
