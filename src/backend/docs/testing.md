# 单元测试与本地中间件

## 推荐流程

```bash
make test-deps-up
make test
make test-deps-down
```

`make test` 始终运行全部 pytest，包括真实 RabbitMQ/Celery 集成用例。缺少中间件时测试会失败，不会静默跳过。

测试中间件使用 `restart: unless-stopped`。首次执行 `make test-deps-up` 后，Docker daemon 重启时会自动恢复容器；Docker Desktop 本身仍需配置为登录后启动。执行 `make test-deps-down` 会删除容器，之后需要重新执行 `make test-deps-up`。

## ARM 环境

官方 MySQL 5.7 镜像仅提供 amd64 架构。Apple Silicon 或其他 arm64 Docker 环境无法运行 amd64 模拟时，使用 ARM MySQL 5.7 镜像：

```bash
TEST_MYSQL_IMAGE=biarms/mysql:5.7 \
TEST_MYSQL_PLATFORM=linux/arm64 \
make test-deps-up
```

GitHub Actions 使用 x86 runner 和官方 `mysql:5.7.44` service，不受本地 Compose 镜像配置影响。

## 不使用 Docker

可自行部署 MySQL 5.7、Redis 6 和 RabbitMQ 3.7.18，并在 `config/local_settings.py` 中设置独立测试库、`CELERY_TEST_BROKER_URL` 和 `CELERY_TEST_QUEUE_PREFIX`。普通 `BROKER_URL` 与真实测试 Broker 相互独立。

## Worktree 隔离

每个 worktree 必须使用不同的 `DATABASES["default"]["TEST"]["NAME"]` 和 `CELERY_TEST_QUEUE_PREFIX`。Redis 继续通过项目 `REDIS_KEY_PREFIX` 隔离。

多个 worktree 可以共享同一个 RabbitMQ Broker，但不能共享 `CELERY_TEST_QUEUE_PREFIX`，否则并发测试可能消费其他 worktree 的任务。

## 重置中间件

`make test-deps-reset` 会删除 Compose 的 MySQL 测试卷并重新创建中间件，只能用于本地测试环境。

## 默认端口

| 服务 | 端口 | 覆盖变量 |
| --- | --- | --- |
| MySQL | 3357 | `TEST_MYSQL_PORT` |
| Redis | 7963 | `TEST_REDIS_PORT` |
| RabbitMQ AMQP | 5672 | `TEST_RABBITMQ_PORT` |
| RabbitMQ 管理端 | 15672 | `TEST_RABBITMQ_MANAGEMENT_PORT` |

MySQL 镜像和平台分别通过 `TEST_MYSQL_IMAGE`、`TEST_MYSQL_PLATFORM` 覆盖。
Compose 会统一将 MySQL server 字符集设置为 `utf8mb4`，避免不同架构镜像的默认字符集差异影响数据迁移和单元测试。
