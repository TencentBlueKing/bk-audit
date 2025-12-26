# 定义公共参数

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