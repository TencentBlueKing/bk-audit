# 权限、用户、流程与通知 API

返回：[API 明细索引](README.md) · [授权总览](../../docs/api_authorization.md)

以下是代码声明的 HTTP 方法与相对路径，未拼接网关环境地址。身份、状态的读法见索引。

模块：[IAM V3 网关封装](#bk_iam) · [IAM V4 网关封装](#bk_iam_v4) · [用户管理](#user_manage) · [PaaS V3](#bk_paas) · [ITSM V3](#bk_itsm) · [ITSM V4](#bk_itsm_v4) · [SOPS 标准运维](#bk_sops) · [CMSI 通知发送](#bk_cmsi)

## bk_iam

**IAM V3 网关封装** · [接口定义](../bk_iam/default.py)

基于 `BKAPP_BK_IAM_APIGW_NAME`，另有 IAM SDK 直接调用，见 [SDK 清单](direct-integrations.md#iam-v3-sdk)
。用户组管理、授权和角色查询根据所用功能分别授权；启 IAM V4 后仍需核对明确保留的 V3 路径。

| Resource                   | 方法     | 相对路径或配置项                                                          | 审计侧身份 | 已见引用                                        |
|----------------------------|----------|---------------------------------------------------------------------------|------------|-------------------------------------------------|
| `GetSystems`               | `GET`    | `/api/v1/open/admin/systems`                                              | SDK 默认   | [代码](../../apps/meta/handlers/system_sync.py) |
| `GetSystemRoles`           | `GET`    | `/api/v1/open/admin/roles/system_managers/systems/{system_id}/members/`   | SDK 默认   | [代码](../../apps/meta/handlers/system_sync.py) |
| `GetSystemInfo`            | `GET`    | `/api/v1/model/share/systems/{system_id}/query`                           | SDK 默认   | [代码](../../apps/meta/handlers/system_sync.py) |
| `CreateGradeManagerGroups` | `POST`   | `/api/v2/open/management/systems/{system_id}/grade_managers/{id}/groups/` | SDK 默认   | [代码](../../apps/meta/handlers/iam_group.py)   |
| `GrantGroupPolicies`       | `POST`   | `/api/v2/open/management/systems/{system_id}/groups/{id}/policies/`       | SDK 默认   | [代码](../../apps/meta/handlers/iam_group.py)   |
| `GetGroupMembers`          | `GET`    | `/api/v2/open/management/systems/{system_id}/groups/{id}/members/`        | SDK 默认   | [代码](../../apps/meta/handlers/iam_group.py)   |
| `AddGroupMembers`          | `POST`   | `/api/v2/open/management/systems/{system_id}/groups/{id}/members/`        | SDK 默认   | [代码](../../apps/meta/handlers/iam_group.py)   |
| `DeleteGroupMembers`       | `DELETE` | `/api/v2/open/management/systems/{system_id}/groups/{id}/members/`        | SDK 默认   | [代码](../../apps/meta/handlers/iam_group.py)   |

## bk_iam_v4

**IAM V4 网关封装** · [接口定义](../bk_iam_v4/default.py)

优先 `BKAPP_BK_IAM_V4_API_URL`，否则 `BKAPP_BKIAM_APIGW_NAME`；多租户缺省 `prod`，单租户生产 `prod`／非生产 `stage`。鉴权请求的
`subject` 与网关认证主体不是一回事。回调读取令牌为应用态，使用 `BKAPP_SYSTEM_TENANT_ID`（默认 `system`
）；普通运行时接口仍按实例租户。模型同步是 [独立管理权限](direct-integrations.md#iam-v4-模型同步)。

| Resource                           | 方法     | 相对路径或配置项                                                                     | 审计侧身份          | 已见引用                                         |
|------------------------------------|----------|--------------------------------------------------------------------------------------|---------------------|--------------------------------------------------|
| `ListSystemResource`               | `GET`    | `/api/v1/open/rbac/share/model/systems/`                                             | SDK 默认            | [代码](../../apps/meta/handlers/system_sync.py)  |
| `RetrieveSystemResource` / `RetrieveCallbackSystemResource` | `GET` | `/api/v1/open/rabc/share/model/systems/{system_id}/` | 系统详情：SDK 默认；回调取 Token：应用（注册租户） | [系统详情](../../apps/meta/handlers/system_sync.py) · [回调取 Token](../../apps/permission/handlers/iam_v4.py) |
| `DirectAuthResource`               | `POST`   | `/api/v1/open/rbac/authorization/systems/{system_id}/auth/`                          | SDK 默认            | [代码](../../apps/permission/handlers/iam_v4.py) |
| `DirectAuthByActionsResource`      | `POST`   | `/api/v1/open/rbac/authorization/systems/{system_id}/auth-by-actions/`               | SDK 默认            | [代码](../../apps/permission/handlers/iam_v4.py) |
| `DirectAuthByResourcesResource`    | `POST`   | `/api/v1/open/rbac/authorization/systems/{system_id}/auth-by-resources/`             | SDK 默认            | [代码](../../apps/permission/handlers/iam_v4.py) |
| `ListAuthorizedResourceResource`   | `POST`   | `/api/v1/open/rbac/authorization/systems/{system_id}/relation/authorized-resources/` | SDK 默认            | [代码](../../apps/permission/handlers/iam_v4.py) |
| `GeneratePermApplyUrlResource`     | `POST`   | `/api/v1/open/application/permission-apply-urls/`                                    | SDK 默认            | [代码](../../apps/permission/handlers/iam_v4.py) |
| `AddAuthorizationResource`         | `POST`   | `/api/v1/open/rbac/mgmt/systems/{system_id}/authorizations/`                         | SDK 默认 + operator | [代码](../../apps/permission/handlers/iam_v4.py) |
| `RevokeAuthorizationResource`      | `DELETE` | `/api/v1/open/rbac/mgmt/systems/{system_id}/authorizations/`                         | SDK 默认 + operator | [代码](../../apps/permission/handlers/iam_v4.py) |
| `ListAuthorizationSubjectResource` | `POST`   | `/api/v1/open/rbac/mgmt/systems/{system_id}/authorizations/query-subject/`           | SDK 默认 + operator | [代码](../../apps/permission/handlers/iam_v4.py) |

## user_manage

**用户管理** · [接口定义](../user_manage/default.py)

单租户常规接口走 ESB，多租户走 `BKAPP_BK_USER_APIGW_NAME`（默认 `bk-user`）的 `prod`。虚拟用户查询是租户管理员解析的前置依赖；当前
SDK 继承 GET。用户快照 Schema 是独立的配置地址与 Basic 凭据，不走业务用户查询路径。

| Resource                         | 方法   | 相对路径或配置项                                                                           | 审计侧身份               | 已见引用                                                                 |
|----------------------------------|--------|--------------------------------------------------------------------------------------------|--------------------------|--------------------------------------------------------------------------|
| `ListUsers`                      | `GET`  | 单 `/list_users/`；多 `/api/v3/open/tenant/users/`                                         | SDK 默认                 | [代码](../../apps/meta/resources.py)                                     |
| `RetrieveUser`                   | `GET`  | 单 `/retrieve_user/`；多 `/api/v3/open/tenant/users/{bk_username}/`                        | SDK 默认                 | [代码](../../apps/meta/resources.py)                                     |
| `ListUserDepartments`            | `GET`  | 单 `/list_profile_departments/`；多 `/api/v3/open/tenant/users/{bk_username}/departments/` | SDK 默认                 | [代码](../../services/web/scene/resources.py)                            |
| `ListDepartments`                | `GET`  | 单 `/list_departments/`；多 `/api/v3/open/tenant/departments/`                             | 平台                     | [代码](../../apps/permission/handlers/resource_types/dept_bk_usermgr.py) |
| `RetrieveDepartment`             | `GET`  | 单 `/retrieve_department/`；多 `/api/v3/open/tenant/departments/{department_id}/`          | 平台                     | [代码](../../services/web/vision/handlers/convertor.py)                  |
| `BatchLookupVirtualUserResource` | `GET`  | 单 `/batch_lookup_virtual_user/`；多 `/api/v3/open/tenant/virtual-users/-/lookup/`         | SDK 默认（内置查询参数） | [代码](../../core/tenant.py)                                             |
| `GetSnapshotSchema`              | `POST` | `/`                                                                                        | Basic（额外头）          | [代码](../../services/web/strategy_v2/resources.py)                      |

## bk_paas

**PaaS V3** · [接口定义](../bk_paas/default.py)

`BKAPP_BK_PAAS_APIGW_NAME` 的 `prod`；用于多平台应用信息查询，自行构造网关应用凭据。

| Resource       | 方法  | 相对路径或配置项                        | 审计侧身份 | 已见引用                             |
|----------------|-------|-----------------------------------------|------------|--------------------------------------|
| `UniAppsQuery` | `GET` | `/system/uni_applications/query/by_id/` | 应用       | [代码](../../apps/meta/resources.py) |

## bk_itsm

**ITSM V3** · [接口定义](../bk_itsm/default.py)

`BKAPP_BK_ITSM_APIGW_NAME`；多租户走 APIGW `prod`，单租户按 `BKAPP_USE_APIGW` 在 APIGW 与 ESB 间选路。新单默认版本由
`BKAPP_ENABLE_ITSM_V4` 选择，与多租户独立；历史单据按自身版本处理，不能只凭新单版本撤掉旧授权。

| Resource              | 方法   | 相对路径或配置项                                                         | 审计侧身份 | 已见引用                                           |
|-----------------------|--------|--------------------------------------------------------------------------|------------|----------------------------------------------------|
| `GetServices`         | `GET`  | APIGW `/v2/itsm/get_services/`；ESB `/get_services/`                     | 平台       | [代码](../../apps/itsm/resources.py)               |
| `GetServiceDetail`    | `GET`  | APIGW `/v2/itsm/get_service_detail/`；ESB `/get_service_detail/`         | 平台       | [代码](../../apps/itsm/resources.py)               |
| `CreateTicket`        | `POST` | APIGW `/v2/itsm/create_ticket/`；ESB `/create_ticket/`                   | 平台       | [代码](../../services/web/risk/handlers/ticket.py) |
| `TicketApproveResult` | `POST` | APIGW `/v2/itsm/ticket_approval_result/`；ESB `/ticket_approval_result/` | 平台       | [代码](../../services/web/risk/handlers/ticket.py) |
| `OperateTicket`       | `POST` | APIGW `/v2/itsm/operate_ticket/`；ESB `/operate_ticket/`                 | 平台       | [代码](../../services/web/risk/resources/risk.py)  |

## bk_itsm_v4

**ITSM V4** · [接口定义](../bk_itsm_v4/default.py)

多租户用 `BKAPP_BK_CW_AITSM_APIGW_NAME`（默认 `cw-aitsm`）的 `prod`；单租户用 `BKAPP_BK_ITSM_V4_APIGW_NAME`。流程列表额外按配置发送
`SYSTEM-TOKEN`，不替代网关凭据。系统／流程创建类接口按初始化需求单独确认，不默认纳入运行态授权。

| Resource               | 方法   | 相对路径或配置项                          | 审计侧身份               | 已见引用                                           |
|------------------------|--------|-------------------------------------------|--------------------------|----------------------------------------------------|
| `TicketCreate`         | `POST` | `/api/v1/ticket/create/`                  | 平台                     | [代码](../../services/web/risk/handlers/ticket.py) |
| `TicketLogs`           | `GET`  | `/api/v1/ticket/logs/`                    | 平台                     | [代码](../../services/web/scene/resources.py)      |
| `SystemWorkflowList`   | `GET`  | `/api/v1/system_workflow/list/`           | 平台 + 可选 SYSTEM-TOKEN | [代码](../../apps/itsm/resources.py)               |
| `Workflows`            | `GET`  | `/api/v1/workflows/`                      | 平台                     | [代码](../../apps/itsm/resources.py)               |
| `TicketDetail`         | `GET`  | `/api/v1/ticket/detail/`                  | 平台                     | [代码](../../services/web/risk/handlers/ticket.py) |
| `TicketHandle`         | `POST` | `/api/v1/ticket/handle/`                  | 平台                     | [代码](../../services/web/risk/resources/risk.py)  |

## bk_sops

**SOPS 标准运维** · [接口定义](../bk_sops/default.py)

`BKAPP_BK_SOPS_APIGW_NAME` 或单租户显式 `BKAPP_BK_SOPS_API_URL`；多租户用该网关的 `prod`。模板读与任务／节点操作分开申请；当前用
SDK 平台态，不等同于切换成租户管理员。

| Resource          | 方法   | 相对路径或配置项                                | 审计侧身份 | 已见引用                                           |
|-------------------|--------|-------------------------------------------------|------------|----------------------------------------------------|
| `GetTemplateList` | `GET`  | `/get_template_list/{bk_biz_id}/`               | 平台       | [代码](../../apps/sops/resources.py)               |
| `GetTemplateInfo` | `GET`  | `/get_template_info/{template_id}/{bk_biz_id}/` | 平台       | [代码](../../apps/sops/resources.py)               |
| `CreateTask`      | `POST` | `/create_task/{template_id}/{bk_biz_id}/`       | 平台       | [代码](../../services/web/risk/handlers/ticket.py) |
| `StartTask`       | `POST` | `/start_task/{task_id}/{bk_biz_id}/`            | 平台       | [代码](../../services/web/risk/handlers/ticket.py) |
| `GetTaskStatus`   | `GET`  | `/get_task_status/{task_id}/{bk_biz_id}/`       | 平台       | [代码](../../services/web/risk/handlers/ticket.py) |
| `OperateTask`     | `POST` | `/operate_task/{task_id}/{bk_biz_id}/`          | 平台       | [代码](../../services/web/risk/resources/risk.py)  |
| `GetNodeData`     | `GET`  | `/get_task_node_data/{bk_biz_id}/{task_id}/`    | 平台       | [代码](../../services/web/risk/resources/risk.py)  |
| `OperateNode`     | `POST` | `/operate_node/{bk_biz_id}/{task_id}/`          | 平台       | [代码](../../services/web/risk/resources/risk.py)  |

## bk_cmsi

**CMSI 通知发送** · [接口定义](../bk_cmsi/default.py)

单租户用 `BKAPP_CMSI_URL` 或 ESB；多租户用 `BKAPP_BK_CMSI_APIGW_NAME`（默认 `bk-cmsi`）的 `prod`
。按实际开通的发送渠道申请；模板中的接收人不是网关认证主体。

| Resource     | 方法   | 相对路径或配置项                            | 审计侧身份 | 已见引用                                    |
|--------------|--------|---------------------------------------------|------------|---------------------------------------------|
| `GetMsgType` | `GET`  | 单 `/get_msg_type/`；多 `/v1/channels/`     | SDK 默认   | [代码](../../apps/notice/resources.py)      |
| `SendMail`   | `POST` | 单 `/send_mail/`；多 `/v1/send_mail/`       | SDK 默认   | [代码](../../apps/notice/senders/mail.py)   |
| `SendRtx`    | `POST` | 单 `/send_rtx/`；多 `/v1/send_rtx/`         | SDK 默认   | [代码](../../apps/notice/senders/rtx.py)    |
| `SendVoice`  | `POST` | 单 `/send_voice_msg/`；多 `/v1/send_voice/` | SDK 默认   | [代码](../../apps/notice/senders/voice.py)  |
| `SendMsg`    | `POST` | 单 `/send_msg/`；多 `/v1/send_sms/`         | SDK 默认   | [代码](../../apps/notice/senders/sms.py)    |
| `SendWeixin` | `POST` | 单 `/send_weixin/`；多 `/v1/send_weixin/`   | SDK 默认   | [代码](../../apps/notice/senders/weixin.py) |
