# 后端 Agent 指引

先读[项目入口](../../AGENTS.md)。本目录维护蓝鲸审计中心的 Python / Django 后端，公共能力导航见[后端能力](../../agent/backend/README.md)。

## 项目速览

- `apps/` 是 Django 业务应用，`services/` 是服务层，`api/` 封装外部 API，`core/` 提供公共能力。
- `config/` 维护环境配置，`tests/` 存放测试，`evals/` 存放 AI 评测，`support-files/` 存放部署支撑文件。
- 项目结构、依赖和启动方式见[后端开发说明](README.md)，进程及 Worker 分层见[进程架构设计](docs/app_desc_design.md)。

## 开发环境与验证

Python 相关操作使用当前项目的 `.venv`，包括启动服务、管理命令、测试和 pre-commit。以下入口在 `src/backend` 执行，实际命令以 [Makefile](Makefile) 和对应配置为准。

| 任务 | 入口 |
| --- | --- |
| 检查本次暂存文件 | `make quality` |
| 常规测试 | `make test` |
| 常规及专项完整验证 | `make test-all` |

- 测试所需中间件及运行方式见[测试指南](docs/testing.md)。按改动范围选择验证，分别记录常规与专项结果。
- bk_resource 测试通过 `.request()` 覆盖序列化器校验链路。尽量完整断言响应，可复用 `assert_list_contains`、`assert_dict_contains`。
- 使用 Django runner 时，测试标签采用 dotted path。Django runner 和 pytest 的测试收集范围不同，按各自入口执行。
- 格式、hook 和提交标题见[pre-commit 指南](docs/pre-commit.md)及[实际配置](.pre-commit-config.yaml)。只暂存本次文件，格式器修改后复核并重新暂存，通过检查再提交。

## 开发约定

- 沿用所属模块的 Resource、Serializer、Service 和权限边界，接口补齐必要的请求与响应校验。
- import 放在文件开头，循环依赖等特殊情况按实际原因处理。优先复用已有枚举、常量和异常。
- 新增或修改 Model 时，同步考虑迁移与 `admin.py`，补齐适用的展示、筛选和搜索配置。
- Resource 模块拆成 package 时，通过 `__init__.py` 保持既有导入路径、导出名称和注册契约兼容。
- 注释说明职责及必要的设计原因。参数、返回值、异常含义不自明时再补充说明，修改代码时同步维护相关注释。

## Worktree 与本地材料

- 开始有状态验证前，核对本 worktree 实际加载的配置。`config/local_settings.py` 使用独立文件。
- 测试库名、Celery 测试队列前缀和 Redis DB 按 worktree 隔离。Redis key prefix 仅作额外隔离，具体要求见[测试指南](docs/testing.md#worktree-隔离)。
- 项目指引从当前 checkout 取得。复用本地环境资源前核对适用范围，清理时确认资源归属。
- 方案、临时材料和验证证据放在 Git 忽略的 `debug/` 专题目录。本地配置、认证、真实业务数据及个人资源信息保留在本地，提交前核对差异与忽略状态。
