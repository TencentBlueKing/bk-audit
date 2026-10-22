# ui-stream 安装与依赖维护

审计的 Python 3.11 环境依赖 [`ui-stream[redis]==0.1.0a4`](https://pypi.org/project/ui-stream/0.1.0a4/)，
导入名为 `ui_stream`。该版本是 alpha 预发布版本；审计通过精确版本声明和 `pdm.lock` 管理依赖，
不在仓库中复制组件源码。Redis extra 与审计现有的 Pydantic 2.10.4、redis-py 3.5.3 配合使用。

## 安装与确认

先按[证书安全边界](python_package_security.md)完成安装工具引导；再在 `src/backend` 使用项目的 PDM 环境同步生产依赖：

```sh
pdm sync --prod
.venv/bin/python -c 'import ui_stream; from importlib.metadata import version; print(version("ui-stream")); print(ui_stream.__file__)'
```

包应从该虚拟环境的 `site-packages` 导入。修改组件时，应在组件项目中开发、测试并发布版本，
再更新审计依赖；不要通过修改安装目录或复制源码改变审计运行时行为。

## 依赖文件的职责

| 文件 | 职责 |
| --- | --- |
| `pyproject.toml` | 声明直接依赖及组件精确版本 |
| `pdm.lock` | 保存完整依赖解析结果和制品哈希 |
| `requirements.txt` | 按项目生产导出规则提供 Docker 安装入口 |

更新依赖后，重新解析并检查锁文件，再导出生产 requirements：

```sh
pdm lock
pdm lock --check
make deps_prod
```

`deps_prod` 使用 `pdm export --pyproject --no-hashes --prod`，导出的是直接依赖声明，
不是完整锁定的传递依赖清单。需要逐项复现完整解析结果时，以 `pdm.lock` 为准。

## Docker 安装

仓库 `Dockerfile` 从 `https://mirrors.tencent.com/pypi/simple` 安装 `requirements.txt`。
目标环境应能访问该索引及其制品地址，并保持 TLS 校验。核验依赖安装时，应让安装步骤实际执行，
例如使用 `docker build --no-cache`，然后在生成的镜像中执行上面的版本与导入检查。

## 接入与升级边界

审计适配层提供原有业务入口，负责 Django 配置、事件模型、MySQL 事务、权限和执行生命周期；
通用缓冲、实时读取与 SSE 编码由组件提供。职责、运行保证、配置及扩展契约统一维护在
[流式传输设计](../services/web/ai_assistant/streaming/README.md)，客户端消费方式见
[前端接入指南](../services/web/ai_assistant/docs/frontend_integration.md#流式附件先快照再增量最后详情)。

alpha 升级按已发布 API 同步迁移适配层，保持公开事件协议和审计异常语义，检查 Runtime、Redis 适配、
归档事务及 SSE 恢复测试，并验证实际镜像中的依赖版本。组件源码、API 和独立测试由
[ui-stream 项目](https://github.com/0RAJA/ui-stream)维护。
