# 定义公共参数

VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PRE_COMMIT ?= $(VENV)/bin/pre-commit

# ── Backend Quality ─────────────────────────────────────

# 为当前 clone 安装只检查暂存文件的 Git pre-commit hook
.PHONY: install-hooks
install-hooks:
	$(PRE_COMMIT) install --install-hooks --config .pre-commit-config.yaml

# 检查 Git 暂存区；与提交时执行范围一致
.PHONY: quality
quality:
	$(PRE_COMMIT) run

# 检查全部受管文件；用于存量治理和本地复现 CI
.PHONY: quality-all
quality-all:
	$(PRE_COMMIT) run --all-files --show-diff-on-failure

.PHONY: test
test:
	$(PYTHON) manage.py test tests/

.PHONY: check
check: quality test

# 默认目标（强制重新生成所有依赖）
.PHONY: all_deps
all_deps: deps_prod deps_dev

# 生成生产环境依赖（强制每次执行）
.PHONY: deps_prod
deps_prod:
	@pdm export --pyproject --no-hashes --prod -o requirements.txt
	@echo "Adding Tencent mirror to requirements.txt"
	@(cat requirements.txt) > requirements.txt.tmp && mv requirements.txt.tmp requirements.txt

# 生成开发环境依赖（强制每次执行）
.PHONY: deps_dev
deps_dev:
	@pdm export --pyproject --no-hashes -G dev --no-default -o requirements_dev.txt
	@echo "Adding Tencent mirror to requirements_dev.txt"
	@(cat requirements_dev.txt) > requirements_dev.txt.tmp && mv requirements_dev.txt.tmp requirements_dev.txt

# 清理生成的文件
.PHONY: clean_deps
clean_deps:
	@rm -f requirements.txt requirements_dev.txt

# ── AI Prompts ──────────────────────────────────────────

# 生成所有 AI 系统提示词
.PHONY: prompts
prompts: prompt-nl2riskfilter

# 生成 NL2RiskFilter 系统提示词
.PHONY: prompt-nl2riskfilter
prompt-nl2riskfilter:
	@python -m services.web.ai.prompts.nl2riskfilter.generate

# ── 测试与本地中间件 ────────────────────────────────────

# 项目依赖会通过 pytest 入口名识别测试进程，因此不能使用 ``python -m pytest``。
# 本地优先使用项目虚拟环境；GitHub Actions 没有 .venv 时使用 setup-python 安装的 pytest。
PYTEST := $(if $(wildcard .venv/bin/pytest),.venv/bin/pytest,pytest)
TEST_COMPOSE := docker compose -f docker-compose.test.yml -p bk-audit-test

.PHONY: test-deps-up test-deps-status test-deps-down test-deps-reset test

test-deps-up:
	$(TEST_COMPOSE) up -d --wait

test-deps-status:
	$(TEST_COMPOSE) ps

test-deps-down:
	$(TEST_COMPOSE) down --remove-orphans

test-deps-reset:
	$(TEST_COMPOSE) down -v --remove-orphans
	$(TEST_COMPOSE) up -d --wait

test:
	$(PYTEST) --cov=. --cov-report=term-missing --cov-report=xml
