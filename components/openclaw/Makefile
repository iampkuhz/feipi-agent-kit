SHELL := /bin/bash

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

.PHONY: deploy deploy-check runtime-check runtime-install skills-check bootstrap test validate doctor mcp-probe weixin-login

deploy:
	@bash scripts/deploy.sh $(if $(YES),--yes,)

deploy-check:
	@bash scripts/deploy.sh --check

bootstrap:
	@OPENCLAW_CONFIG_PATH="$(REPO_ROOT)/openclaw.json" bash scripts/bootstrap.sh $(if $(SKILL),--manifest "$(SKILL)",)

skills-check:
	@OPENCLAW_CONFIG_PATH="$(REPO_ROOT)/openclaw.json" bash scripts/bootstrap.sh --dry-run $(if $(SKILL),--manifest "$(SKILL)",)

runtime-check:
	@bash scripts/install-runtime.sh --check

runtime-install:
	@bash scripts/install-runtime.sh --write $(if $(YES),--yes,)

test:
	@bash tests/test-deploy.sh
	@bash tests/test-runtime-install.sh
	@bash tests/test-bootstrap.sh
	@bash tests/test-weixin-login.sh

weixin-login:
	@bash scripts/weixin-login.sh

validate:
	@$(MAKE) test
	@OPENCLAW_CONFIG_PATH="$(REPO_ROOT)/openclaw.json" bash scripts/validate-config.sh

doctor:
	@bash scripts/doctor.sh

mcp-probe:
	@openclaw mcp doctor --probe
