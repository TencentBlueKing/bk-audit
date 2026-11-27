# 数据平台与日志 API

返回：[API 明细索引](README.md) · [授权总览](../../docs/api_authorization.md)

以下是代码声明的 HTTP 方法与相对路径，未拼接网关环境地址。身份、状态的读法见索引。

模块：[BKBase V3](#bk_base) · [BKBase V4](#bk_base_v4) · [BKLog 日志平台](#bk_log)

## bk_base

**BKBase V3** · [接口定义](../bk_base/default.py)

单租户使用 `BKAPP_BASE_API_URL` 或 `BKAPP_BK_BASE_APIGW_NAME` 生成的地址；多租户 `bk-base`（默认网关名）走 `prod`。
`BKAPP_BKBASE_API_VERSION` 默认 `v3`；选 V4 不代表所有 V3 路径都能撤权。查询同时供 V3／V4 使用，三种 Query 封装共用
`BKAPP_BKBASE_QUERY_SYNC_ACTION`（默认 `/v3/queryengine/query_sync/`）；单租户 Debug 可用独立地址。一起核对数据源、清洗／入库、Flow、结果表及
SQL 查询的授权边界。

V3 平台 Resource 仍可能在业务参数中附带平台用户名，即使多租户网关头已经改用租户管理员。联调时分别核对网关身份与接口参数。

| Resource                       | 方法     | 相对路径或配置项                                                   | 审计侧身份               | 已见引用                                         |
|--------------------------------|----------|--------------------------------------------------------------------|--------------------------|--------------------------------------------------|
| `DatabusStoragesPost`          | `POST`   | `/v3/databus/data_storages/`                                       | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/storage.py)     |
| `DatabusStoragesPut`           | `PUT`    | `/v3/databus/data_storages/{result_table_id}/`                     | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/storage.py)     |
| `DatabusCleansPost`            | `POST`   | `/v3/databus/cleans/`                                              | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/clean.py)       |
| `DatabusCleansPut`             | `PUT`    | `/v3/databus/cleans/{processing_id}/`                              | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/clean.py)       |
| `DatabusCleansDelete`          | `DELETE` | `/v3/databus/cleans/{processing_id}/`                              | 平台                     | [代码](../../services/web/bkbase/clean.py)       |
| `DatabusTasksPost`             | `POST`   | `/v3/databus/tasks/`                                               | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/clean.py)       |
| `DatabusTasksDelete`           | `DELETE` | `/v3/databus/tasks/{processing_id}/`                               | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/clean.py)       |
| `CreateResourceSet`            | `POST`   | `/v3/resourcecenter/resource_sets/`                                | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/storage.py)     |
| `UpdateResourceSet`            | `PATCH`  | `/v3/resourcecenter/resource_sets/{resource_set_id}/`              | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/storage.py)     |
| `CleanPreview`                 | `POST`   | `/v3/databus/cleans/verify/`                                       | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/clean.py)       |
| `CreateDeployPlan`             | `POST`   | `/v3/access/deploy_plan/`                                          | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/source.py)      |
| `UpdateDeployPlan`             | `PUT`    | `/v3/access/deploy_plan/{bkbase_data_id}/`                         | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/source.py)      |
| `StopCollector`                | `POST`   | `/v3/access/collectorhub/{bkbase_data_id}/stop/`                   | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/source.py)      |
| `GetScenePlans` / `CheckAiops` | `GET` | `/v3/aiops/scene_service/plans/` | 平台 | [方案列表／能力探测](../../services/web/bkbase/deprecated.py) |
| `GetPlanDetail`                | `GET`    | `/v3/aiops/scene_service/plans/{plan_id}/`                         | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/deprecated.py)  |
| `AuthTickets` | `POST` | `/v3/auth/tickets/` | 平台 | [仅 V3，AIOps 结果表授权](../../services/web/analyze/controls/auth.py#L54) |
| `CreateFlow`                   | `POST`   | `/v3/dataflow/flow/flows/`                                         | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `StartFlow`                    | `POST`   | `/v3/dataflow/flow/flows/{flow_id}/start/`                         | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `RestartFlow`                  | `POST`   | `/v3/dataflow/flow/flows/{flow_id}/restart/`                       | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `StopFlow`                     | `POST`   | `/v3/dataflow/flow/flows/{flow_id}/stop/`                          | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `GetFlowGraph`                 | `GET`    | `/v3/dataflow/flow/flows/{flow_id}/graph/`                         | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `CreateFlowNode`               | `POST`   | `/v3/dataflow/flow/flows/{flow_id}/nodes/`                         | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `UpdateFlowNode`               | `PUT`    | `/v3/dataflow/flow/flows/{flow_id}/nodes/{node_id}/`               | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `DeleteFlowNode`               | `DELETE` | `/v3/dataflow/flow/flows/{flow_id}/nodes/{node_id}/`               | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `GetRtFields`                  | `GET`    | `/v3/meta/result_tables/{result_table_id}/fields/`                 | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/metadata.py)    |
| `GetFlowDeployData`            | `GET`    | `/v3/dataflow/flow/flows/{flow_id}/latest_deploy_data/`            | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `GetRawdataList`               | `GET`    | `/v3/access/rawdata/`                                              | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/source.py)      |
| `GetMyRawdataList`             | `GET`    | `/v3/access/rawdata/mine/`                                         | 个人                     | [代码](../../services/web/bkbase/source.py)      |
| `GetRawdataDetail`             | `GET`    | `/v3/access/rawdata/{bk_data_id}/`                                 | 个人                     | [代码](../../services/web/bkbase/source.py)      |
| `GetRawdataTail`               | `GET`    | `/v3/databus/rawdatas/{bk_data_id}/tail/`                          | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/source.py)      |
| `GetResultTables`              | `GET`    | `/v3/meta/result_tables/`                                          | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/metadata.py)    |
| `GetMineResultTables`          | `GET`    | `/v3/meta/result_tables/mine/`                                     | 个人                     | [代码](../../services/web/bkbase/permissions.py) |
| `GetResultTable`               | `GET`    | `/v3/meta/result_tables/{result_table_id}/`                        | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/metadata.py)    |
| `GetProjectData`               | `GET`    | `/v3/auth/projects/{project_id}/data/`                             | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/permissions.py) |
| `ProjectDataBatchCheck` | `POST` | `/v3/auth/projects/{project_id}/data/batch_check/` | 多：租户管理员；单：平台 | [仅 V3，检查结果表项目授权](../../services/web/bkbase/permissions.py#L285) |
| `ProjectDataBatchAdd` | `POST` | `/v3/auth/projects/{project_id}/data/batch_add/` | 多：租户管理员；单：平台 | [仅 V3，将结果表授权给策略项目](../../services/web/bkbase/permissions.py#L290) |
| `GetAlertConfigs`              | `GET`    | `/v3/datamanage/dmonitor/alert_configs/{object_type}/{object_id}/` | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `EditAlertConfigs`             | `PATCH`  | `/v3/datamanage/dmonitor/alert_configs/{alert_config_id}/`         | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `GetRoleUsersList`             | `GET`    | `/v3/auth/roles/{role_id}/users/`                                  | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/permissions.py) |
| `GetSensitivityInfoViaDataset` | `GET`    | `/v3/auth/sensitivity/retrieve_dataset/`                           | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/metadata.py)    |
| `QuerySyncResource` / `SafeQuerySyncResource` | `POST` | `BKAPP_BKBASE_QUERY_SYNC_ACTION` | 多：租户管理员；单：平台 | [普通／受控查询](../../services/web/bkbase/query.py) |
| `DebugQuerySyncResource` | `POST` | `BKAPP_BKBASE_QUERY_SYNC_ACTION` | 多：租户管理员；单：平台 | [调试查询](../../services/web/bkbase/query.py)；单租户配置独立 Debug 地址时，按实际网关单独核对 |
| `DataflowBatchStatusList`      | `GET`    | `/v3/dataflow/batch/data_makeup/status_list/`                      | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)        |
| `UserAuthCheck`                | `POST`   | `/v3/auth/users/{user_id}/check/`                                  | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/permissions.py) |
| `UserAuthBatchCheck`           | `POST`   | `/v3/auth/users/batch_check/`                                      | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/permissions.py) |
| `GetBizsList`                  | `GET`    | `/v3/auth/users/scope_dimensions/`                                 | 个人                     | [代码](../../services/web/bkbase/permissions.py) |

## bk_base_v4

**BKBase V4** · [接口定义](../bk_base_v4/default.py)

与 V3 共用 BKBase 网关配置；多租户走 `prod`，URL／请求体中的租户与实例绑定值校验一致。项目、Dataset 和数据源的个人列表／详情有独立
`User*` 封装；同路径的服务端操作仍可能用平台身份。`DirectAuthByResources` 用应用凭据查指定负责人权限，不是使用该负责人的凭据。

| Resource                   | 方法     | 相对路径或配置项                                                   | 审计侧身份               | 已见引用                                                   |
|----------------------------|----------|--------------------------------------------------------------------|--------------------------|------------------------------------------------------------|
| `DirectAuthByResources`    | `POST`   | `/v4/auth/users/direct_auth_by_resources/`                         | 应用                     | [代码](../../services/web/bkbase/permissions.py)           |
| `BatchStatusList`          | `GET`    | `/v4/dataflow/batch/jobs/{job_id}/status_list/`                    | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)                  |
| `ResultTableInfo`          | `GET`    | `/v4/result_tables/{result_table_id}/`                             | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/metadata.py)              |
| `DatasetDetail`            | `GET`    | `/v4/databus/dataset/{namespace}/detail/{dataset_name}/`           | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/metadata.py)              |
| `DatasetList` / `UserDatasetList` | `GET` | `/v4/databus/dataset/{namespace}/dataset_list/` | 普通：平台（多租户用租户管理员）；个人：当前用户 | [Dataset 查询](../../services/web/bkbase/metadata.py#L424) |
| `StorageAssetCreate`       | `POST`   | `/v4/res_manage/assets/storage/`                                   | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/storage.py)               |
| `StorageAssetGet`          | `GET`    | `/v4/res_manage/assets/{project_name}/{sub_type}/{asset_name}/`    | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/storage.py)               |
| `StorageAssetList`         | `GET`    | `/v4/res_manage/assets/`                                           | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/storage.py)               |
| `NamespacesList` / `UserNamespacesList` | `GET` | `/v4/tenants/{tenant}/namespaces` | 普通：平台（多租户用租户管理员）；个人：当前用户 | [项目查询](../../services/web/bkbase/permissions.py#L45) |
| `DataSourceList` / `UserDataSourceList` | `GET` | `/v4/tenants/{tenant}/namespaces/{namespace}/datasources/` | 普通：平台（多租户用租户管理员）；个人：当前用户 | [数据源查询](../../services/web/bkbase/source.py) |
| `DataSourceGet` / `UserDataSourceGet` | `GET` | `/v4/tenants/{tenant}/namespaces/{namespace}/datasources/{name}/` | 普通：平台（多租户用租户管理员）；个人：当前用户 | [数据源详情](../../services/web/bkbase/source.py) |
| `DataSourceCreate`         | `POST`   | `/v4/tenants/{tenant}/namespaces/{namespace}/datasources/`         | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/source.py)                |
| `DataConnCreate`           | `POST`   | `/v4/tenants/{tenant}/namespaces/{namespace}/dataconns/`           | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/source.py)                |
| `DataSourceUpdate`         | `PUT`    | `/v4/tenants/{tenant}/namespaces/{namespace}/datasources/{name}/`  | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/snapshot_restore.py)      |
| `DataConnGet`              | `GET`    | `/v4/tenants/{tenant}/namespaces/{namespace}/dataconns/{name}/`    | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/snapshot_restore.py)      |
| `DataConnUpdate`           | `PUT`    | `/v4/tenants/{tenant}/namespaces/{namespace}/dataconns/{name}/`    | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/snapshot_restore.py)      |
| `DataSourceNotifies`       | `GET`    | `/v4/databus/data_source/notifies/`                                | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)                  |
| `DataSourceNotifiesUpdate` | `PUT`    | `/v4/databus/data_source/notifies/`                                | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)                  |
| `DataIdTail`               | `GET`    | `/v4/namespaces/{namespace}/dataids/{name}/tail_kafka/`            | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/source.py)                |
| `DataIdGet`                | `GET`    | `/v4/namespaces/{namespace}/dataids/{name}/`                       | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/asset_etl_maintenance.py) |
| `ResultTableResourceGet`   | `GET`    | `/v4/namespaces/{namespace}/resulttables/{name}/`                  | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/asset_etl_maintenance.py) |
| `CleanDebug`               | `POST`   | `/v4/databus/clean/debug/`                                         | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/clean.py)                 |
| `CleanGet`                 | `GET`    | `/v4/tenants/{tenant}/namespaces/{namespace}/cleans/{name}/`       | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/asset_etl_maintenance.py) |
| `CleanList`                | `GET`    | `/v4/tenants/{tenant}/namespaces/{namespace}/cleans/`              | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/source.py)                |
| `CleanCreate`              | `POST`   | `/v4/tenants/{tenant}/namespaces/{namespace}/cleans/`              | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/clean.py)                 |
| `CleanUpdate`              | `PUT`    | `/v4/tenants/{tenant}/namespaces/{namespace}/cleans/{name}/`       | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/asset_etl_maintenance.py) |
| `CleanDelete`              | `DELETE` | `/v4/tenants/{tenant}/namespaces/{namespace}/cleans/{name}/`       | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/clean.py)                 |
| `DataStorageGet`           | `GET`    | `/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/{name}/` | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/asset_etl_maintenance.py) |
| `DataStorageList`          | `GET`    | `/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/`        | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/source.py)                |
| `DataStorageCreate`        | `POST`   | `/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/`        | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/storage.py)               |
| `DataStorageUpdate`        | `PUT`    | `/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/{name}/` | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/asset_etl_maintenance.py) |
| `FlowGet`                  | `GET`    | `/v4/tenants/{tenant}/namespaces/{namespace}/flows/{name}/`        | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)                  |
| `FlowCreate`               | `POST`   | `/v4/tenants/{tenant}/namespaces/{namespace}/flows/`               | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)                  |
| `FlowUpdate`               | `PUT`    | `/v4/tenants/{tenant}/namespaces/{namespace}/flows/{name}/`        | 多：租户管理员；单：平台 | [代码](../../services/web/bkbase/flow.py)                  |

## bk_log

**BKLog 日志平台** · [接口定义](../bk_log/default.py)

多租户用 `BKAPP_LOG_APIGW_NAME`（默认 `log-search`）的 `prod`，单租户可能走 APIGW、自定义地址或 ESB。除显式例外，Resource
多租户默认替换为租户管理员。`GetReportToken`／`GetReportHost` 是 SDK 平台态，不应算作个人态；OTLP、自定义直报、ES
检索与存储管理按部署能力选择。

| Resource                      | 方法     | 相对路径或配置项                                                                                   | 审计侧身份                   | 已见引用                                                         |
|-------------------------------|----------|----------------------------------------------------------------------------------------------------|------------------------------|------------------------------------------------------------------|
| `CreateStorage`               | `POST`   | `/databus_storage/`                                                                                | 多：租户管理员；单：平台     | [代码](../../services/web/databus/storage/resources.py)          |
| `UpdateStorage`               | `PUT`    | `/databus_storage/{cluster_id}/`                                                                   | 多：租户管理员；单：平台     | [代码](../../services/web/databus/storage/resources.py)          |
| `DeleteStorage`               | `DELETE` | `/databus_storage/{cluster_id}/`                                                                   | 多：租户管理员；单：平台     | [代码](../../services/web/databus/storage/resources.py)          |
| `GetStorages`                 | `GET`    | `/databus_storage/?bk_biz_id={bk_biz_id}`                                                          | 多：租户管理员；单：平台     | [代码](../../services/web/databus/storage/handler/es.py)         |
| `ConnectivityDetect`          | `POST`   | `/databus_storage/connectivity_detect/?bk_biz_id={bk_biz_id}`                                      | 多：租户管理员；单：平台     | [代码](../../services/web/databus/storage/views.py)              |
| `BatchConnectivityDetect`     | `POST`   | `/databus_storage/batch_connectivity_detect/?bk_biz_id={bk_biz_id}`                                | 多：租户管理员；单：平台     | [代码](../../services/web/databus/storage/handler/es.py)         |
| `NodeAttrs`                   | `POST`   | `/databus_storage/node_attrs/`                                                                     | 多：租户管理员；单：平台     | [代码](../../services/web/databus/storage/views.py)              |
| `BizsList`                    | `GET`    | `/meta/projects/mine/`                                                                             | 个人                         | [代码](../../apps/meta/resources.py)                             |
| `BizTopos`                    | `GET`    | `/bizs/{bk_biz_id}/topo/`                                                                          | 多：租户管理员；单：SDK 默认 | [代码](../../apps/meta/views/biz_views.py)                       |
| `GetHostInstanceByNode`       | `POST`   | `/bizs/{bk_biz_id}/host_instance_by_node/`                                                         | 多：租户管理员；单：SDK 默认 | [代码](../../apps/meta/views/biz_views.py)                       |
| `GetHostInstanceByIP`         | `POST`   | `/bizs/{bk_biz_id}/host_instance_by_ip/`                                                           | 多：租户管理员；单：SDK 默认 | [代码](../../apps/meta/views/biz_views.py)                       |
| `ListAgentStatus`             | `POST`   | `/bizs/{bk_biz_id}/list_agent_status/`                                                             | 多：租户管理员；单：SDK 默认 | [代码](../../apps/meta/views/biz_views.py)                       |
| `GetTemplateTopos`            | `GET`    | `/bizs/{bk_biz_id}/template_topo/`                                                                 | 多：租户管理员；单：SDK 默认 | [代码](../../apps/meta/views/biz_views.py)                       |
| `GetNodesByTemplate`          | `GET`    | `/bizs/{bk_biz_id}/get_nodes_by_template/`                                                         | 多：租户管理员；单：SDK 默认 | [代码](../../apps/meta/views/biz_views.py)                       |
| `CreateCollector`             | `POST`   | `/databus_collector_plugins/{collector_plugin_id}/instances/`                                      | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/resources.py)        |
| `UpdateCollector`             | `PUT`    | 单 `/databus_collector_plugins/update_instance/`；多 `/databus/collector_plugins/update_instance/` | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/resources.py)        |
| `ListBcsClusters`             | `GET`    | `/databus_collectors/list_bcs_clusters/?bk_biz_id={bk_biz_id}`                                     | 多：租户管理员；单：SDK 默认 | [代码](../../apps/meta/views/biz_views.py)                       |
| `ValidateContainerConfigYaml` | `POST`   | `/databus_collectors/validate_container_config_yaml/`                                              | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/views.py)            |
| `CreateCollectorNormal`       | `POST`   | `/databus_collectors/`                                                                             | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/resources.py)        |
| `UpdateCollectorNormal`       | `PUT`    | `/databus_collectors/{collector_config_id}/`                                                       | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/resources.py)        |
| `GetCollector`                | `GET`    | `/databus_collectors/{collector_config_id}/`                                                       | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/resources.py)        |
| `GetSubscriptTaskStatus`      | `GET`    | `/databus_collectors/{collector_config_id}/task_status/?task_id_list={task_id_list}`               | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/views.py)            |
| `GetSubscriptTaskDetail`      | `GET`    | `/databus_collectors/{collector_config_id}/task_detail/?instance_id={instance_id}`                 | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/views.py)            |
| `RetrySubscriptTask`          | `POST`   | `/databus_collectors/{collector_config_id}/retry/`                                                 | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/views.py)            |
| `GetSubscriptionStatus`       | `GET`    | `/databus_collectors/{collector_config_id}/subscription_status/`                                   | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/views.py)            |
| `BatchSubscriptionStatus`     | `GET`    | `/databus_collectors/batch_subscription_status/`                                                   | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/views.py)            |
| `GetCollectorTailLog` / `GetApiPushTailLog` | `GET` | `/databus_collectors/{collector_config_id}/tail/` | 多：租户管理员；单：普通 SDK 默认，直报平台 | [采集日志](../../services/web/databus/collector/handlers.py) · [直报日志](../../services/web/databus/collector/resources.py) |
| `StopSubscription`            | `POST`   | `/databus_collectors/{collector_config_id}/stop/`                                                  | 多：租户管理员；单：SDK 默认 | [代码](../../services/web/databus/collector/resources.py)        |
| `GetGlobals`                  | `GET`    | `/meta/globals/`                                                                                   | 多：租户管理员；单：SDK 默认 | [代码](../../apps/meta/utils/globals.py)                         |
| `CreateCollectorPlugin`       | `POST`   | `/databus_collector_plugins/`                                                                      | 多：租户管理员；单：平台     | [代码](../../services/web/databus/collector_plugin/resources.py) |
| `UpdateCollectorPlugin`       | `PUT`    | `/databus_collector_plugins/{collector_plugin_id}/`                                                | 多：租户管理员；单：平台     | [代码](../../services/web/databus/collector_plugin/resources.py) |
| `PreCheckCollectorEnName`     | `GET`    | `/databus_collectors/pre_check/`                                                                   | 多：租户管理员；单：平台     | [代码](../../services/web/databus/collector/views.py)            |
| `EsQuerySearchResource`       | `POST`   | `/esquery_search/`                                                                                 | 多：租户管理员；单：平台     | [代码](../../services/web/query/resources/es.py)                 |
| `EsQueryScroll`               | `POST`   | `/esquery_scroll/`                                                                                 | 多：租户管理员；单：平台     | [代码](../../services/web/risk/handlers/event.py)                |
| `IndexSetReplace`             | `POST`   | `/index_set/replace/`                                                                              | 多：租户管理员；单：平台     | [代码](../../services/web/databus/collector_plugin/resources.py) |
| `IndexSetOperators` | `GET` | `/search_index_set/operators/` | 多：租户管理员；单：SDK 默认 | [检索操作符](../../services/web/query/views.py#L28) |
| `CheckAllowed`                | `POST`   | `/iam/meta/check_allowed/`                                                                         | 个人                         | [代码](../../apps/permission/resources.py)                       |
| `GetApplyData`                | `POST`   | `/iam/meta/get_apply_data/`                                                                        | 个人                         | [代码](../../apps/permission/resources.py)                       |
| `GetSpacesMine`               | `GET`    | `/meta/spaces/mine/`                                                                               | 个人                         | [代码](../../apps/meta/resources.py)                             |
| `CreateApiPush` | `POST` | `/databus_custom_create/` | 多：租户管理员；单：平台 | [创建 API Push](../../services/web/databus/collector/resources.py#L844)；继承 `CreateCustomCollector`，同一路径只申请一次 |
| `GetReportToken`              | `GET`    | `/databus_collectors/{collector_config_id}/report_token/`                                          | 平台                         | [代码](../../services/web/databus/collector/resources.py)        |
| `GetReportHost`               | `GET`    | `/databus_collectors/report_host/`                                                                 | 平台                         | [代码](../../apps/feature/plugins.py)                            |
