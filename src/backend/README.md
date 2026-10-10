# 审计中心后端（bk-audit backend）

## 快速导航

| 文档 | 说明 |
|------|------|
| [进程架构设计](docs/app_desc_design.md) | Worker 分层策略、Queue 设计决策、新任务接入规则 |
| [AI 助手可观测性](docs/ai_assistant_observability.md) | AI 助手的监控、日志、指标设计 |
| [API 接口与环境配置](docs/api_endpoints_env.md) | 接口地址、环境变量说明 |
| [测试指南](docs/testing.md) | 单元测试运行方式与规范 |
| [Pre-commit 配置](docs/pre-commit.md) | 代码提交前的检查与格式化 |

## 项目结构

```
src/backend/
├── app_desc.yaml          # 进程部署描述（Worker、Web、Beat 等）
├── settings.py            # Django 项目配置入口
├── config/                # 环境配置（default / dev / stag / prod）
├── apps/                  # Django 业务应用
├── services/              # 服务层（web / puller）
├── api/                   # 外部 API 调用封装
├── core/                  # 公共基础模块（中间件、序列化器、工具等）
├── docs/                  # 后端专用文档
├── tests/                 # 单元测试
├── support-files/         # 部署支撑文件（supervisor、apigw、iam 等）
└── evals/                 # AI 能力评测
```

## 本地开发

```bash
# 安装依赖
pip install -r requirements.txt -r requirements_dev.txt

# 数据库迁移
python manage.py migrate

# 启动开发服务器
python manage.py runserver

# 启动 Celery Worker（本地调试）
python manage.py celery worker -O fair -l info -Q celery,default -P gevent -c 4 -E
```

## 相关配置

- **Python 版本**：见 `runtime.txt`
- **依赖管理**：`pyproject.toml` + `pdm.lock`（生产依赖见 `requirements.txt`）
- **部署描述**：`app_desc.yaml`（详见 [进程架构设计](docs/app_desc_design.md)）
