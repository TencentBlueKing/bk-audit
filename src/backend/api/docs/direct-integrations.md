# SDK、直连与回调授权

返回：[API 明细索引](README.md) · [授权总览](../../docs/api_authorization.md)

## IAM V3 SDK

[Permission handler](../../apps/permission/handlers/permission.py) 使用 IAM SDK，应用凭据和地址由审计配置提供，多租户按实例租户传给
SDK。不要只申请 [`api.bk_iam` 封装](identity-and-workflow.md#bk_iam)。下表按仓库调用和当前 SDK 实现归纳，最终以部署依赖版本和上游登记的资源名为准。

| 用途                   | 方法与路径                                                                                                                  | 范围                                                                                                                            |
|------------------------|-----------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| 运行时策略查询         | POST `/api/v2/policy/systems/{system_id}/query/`、`/api/v2/policy/systems/{system_id}/query_by_actions/`                    | 权限检查；目标用户在 IAM 请求中，调用凭据是应用身份。                                                                           |
| 申请链接与系统模型读取 | POST `/api/v1/open/application/`；GET `/api/v1/model/systems/{system_id}/query`                                             | 运行态按业务需求申请。                                                                                                          |
| 资源创建者授权         | POST `/api/v1/open/authorization/resource_creator_action/`、`/api/v1/open/authorization/resource_creator_action_attribute/` | 写权限，和只读鉴权分开。                                                                                                        |
| 路径权限授予／移除     | POST `/api/v1/open/authorization/path/`                                                                                     | 写权限；按调用场景核对。                                                                                                        |
| 资源回调校验凭据       | GET `/api/v1/model/systems/{system_id}/token`                                                                               | IAM V3 回调链路。V4 不用这个接口。                                                                                              |
| 初始化或模型变更       | SDK 的系统模型、资源类型、操作和相关配置管理接口                                                                            | 必要时由 [V3 迁移命令](../../apps/permission/management/commands/iam_migrate.py)／Django 历史数据迁移执行，不按运行态整组授予。 |

IAM V4 并不保证所有 V3 授权都可撤掉；兼容入口和影子对比以实际启用的配置和调用代码为准。

## IAM V4 模型同步

[`iam_v4_migrate`](../../support-files/iam_v4/README.md) 用 [ModelClient](../../apps/permission/iam_v4_model/client.py)
直连明确配置的 `BKAPP_BK_IAM_V4_API_URL`。使用审计应用凭据，多租户在注册租户（`BKAPP_SYSTEM_TENANT_ID`，默认 `system`
）操作。它不是普通运行时鉴权，也不通过 `api.bk_iam_v4` 的常规授权 Resource 发起。

下表以 `/api/v1/open/rbac/model/systems/`
为路径前缀；精确写操作以 [同步计划](../../apps/permission/iam_v4_model/reconcile.py) 为准。

| 相对前缀的路径                                              | 方法         | 用途                                       |
|-------------------------------------------------------------|--------------|--------------------------------------------|
| 集合根路径                                                  | POST         | 创建缺失的系统模型。                       |
| `{system_id}/`                                              | GET、PUT     | 读取系统或更新其元数据；不删除系统。       |
| `{system_id}/{resource-types、actions 或 roles}/`           | GET、POST    | 读取资源类型／操作／角色列表，或创建条目。 |
| `{system_id}/{resource-types、actions 或 roles}/{item_id}/` | PUT、DELETE  | 更新或移除已登记条目。                     |
| `{system_id}/roles/{role_id}/actions/`                      | POST、DELETE | 增删角色操作关系。                         |

预览只读，应用模式可能删除模型条目；不要以“授权接口都在 IAM
V4”为由给常驻服务配置模型写权限。运行时有动态授权业务时，另核对 [
`authorizations` 接口](identity-and-workflow.md#bk_iam_v4)。

## IAM 入站资源回调

- **方向**：IAM → 审计，`POST /api/v1/iam/resources/`。网关 API 的出站授权不能代替回调入口的网络可达、租户路由和回调凭据。
- **校验**：V3 使用 SDK；V4 使用审计应用身份向注册租户读取同一系统的回调令牌，复用系统详情路径
  `GET /api/v1/open/rabc/share/model/systems/{system_id}/`、`fields=system_info`
  。取令牌的注册租户和入站资源的目标租户不是一回事。[鉴权实现](../../apps/permission/handlers/iam_v4.py) · [路由注册](../../apps/permission/urls.py)
- **验收**：使用上游合法的测试回调，确认回调命中正确的租户实例；系统模型写入成功不等于资源回调成功。

## 其他直连或独立认证

| 依赖                       | 接入与授权方式                                                                                                                                           | 代码                                                                                                              |
|----------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| 资源类型 Schema／HTTP Pull | 目标由业务系统的资源类型配置决定。审计用该系统配置的凭据 POST 查询 Schema 或预检取数；数据平台侧的正式 Pull 还需在发布环境核对网络白名单和对应服务凭据。 | [Schema](../../apps/meta/resources.py#L885) · [Pull 预检](../../services/web/databus/collector/resources.py#L547) |
| API 工具执行               | 按工具配置的方法和目标发起 HTTP 调用。按工具单独确认目标、凭据和授权范围，不当成一个共享 APIGW 资源申请。                                                | [工具执行器](../../services/web/tool/executor/tool.py#L509)                                                       |
| 用户快照 Schema            | 使用 `BKAPP_FETCH_USER_INFO_URL` 和 `BKAPP_FETCH_USER_INFO_TOKEN` 访问配置的服务；独立于用户管理平台的用户、部门查询。                                   | [User Manage Resource](../user_manage/default.py#L142)                                                            |
| 监控自定义指标／事件       | 配置监控代理地址与通道凭据（data_id／token）；不等同于给审计 appcode 开通告警策略权限。                                                                  | [上报 Resource](../bk_monitor/default.py#L177)                                                                    |
| Elasticsearch              | 部分查询或运维操作由 Elasticsearch 客户端直连，使用存储实例的权限和网络策略，不走 BKLog API 授权。                                                       | [ES 客户端](../../services/web/query/utils/elastic.py)                                                            |
| 登录与 KMS                 | 登录／会话跟随部署的 PaaS 和登录 SDK，按部署环境确认；当前审计 KMS 是本地解密注入，不是需要申请的 HTTP 网关 API。                                        | [租户中间件](../../core/middleware/tenant_router.py) · [KMS](../../core/kms.py)                                   |

仓库还附带 [旧版组件 SDK](../../blueking/component/collections.py)
和 [评测用 LLM 访问客户端](../../evals/providers/bk_llm_provider.py)。本次没有将前者的未确认运行态调用、后者的评测环境依赖纳入常驻审计服务授权。
