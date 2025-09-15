**API Endpoint 环境变量说明**

- 目的：支持不同环境相同 API 来源的 `api_name` 不一致，通过环境变量统一覆盖，各服务默认值与当前环境保持兼容。
- 位置：集中定义于 `config/default.py` 的“API Endpoint Names (env overrides)”区块；在 `api/domains.py` 中统一读取
  `settings` 并构造各服务的基础 API URL。

**核心行为**

- 优先级：具体 URL 覆盖变量 > 通过 `api_name` 动态构造
    - 若存在 URL 覆盖变量（如 `BKAPP_LOG_API_URL`），直接使用该 URL。
    - 否则使用 `get_endpoint(api_name, provider, stage)` 构造。
- APIGW/ESB 选择：由 `BKAPP_USE_APIGW` 控制（部分服务）。
- 阶段选择：`get_endpoint` 在未显式传入 `stage` 时，会根据是否生产环境自动选择 `stag` 或 `prod`；部分调用点已显式传入
  `stag`（如 `stage`/`stag-new`）或 `stage="prod"`。

**环境变量清单（带默认值）**

- APIGW 名称覆盖
    - `BKAPP_BK_IAM_APIGW_NAME` = `bk-iam`
    - `BKAPP_LOG_APIGW_NAME` = `log-search`
    - `BKAPP_BK_PAAS_APIGW_NAME` = `bkpaas3`
    - `BKAPP_BK_BASE_APIGW_NAME` = `bk-base`
    - `BKAPP_BK_MONITOR_APIGW_NAME` = `bkmonitorv3`
    - `BKAPP_DEVSECOPS_APIGW_NAME` = `devsecops`
    - `BKAPP_BK_SOPS_APIGW_NAME` = `bk-sops`
    - `BKAPP_BK_ITSM_APIGW_NAME` = `bk-itsm`
    - `BKAPP_BKIAM_APIGW_NAME` = `bkiam`
    - `BKAPP_BK_VISION_API_NAME` = `bk-vision`

- ESB 组件名称覆盖
    - `BKAPP_BK_LOG_ESB_NAME` = `bk_log`
    - `BKAPP_USERMANAGE_ESB_NAME` = `usermanage`
    - `BKAPP_MONITOR_V3_ESB_NAME` = `monitor_v3`
    - `BKAPP_ITSM_ESB_NAME` = `itsm`
    - `BKAPP_CMSI_ESB_NAME` = `cmsi`

- 直接 URL 覆盖（存在时优先生效）
    - `BKAPP_LOG_API_URL`
    - `BKAPP_CMSI_URL`
    - `BKAPP_BASE_API_URL`
    - `BKAPP_BK_VISION_API_URL`

- 开关/其他
    - `BKAPP_USE_APIGW`：是否优先走 APIGW（部分服务生效）。

**各服务构造逻辑摘要**

- BK IAM（权限中心）：`BK_IAM_API_URL` = APIGW，`api_name`= `BKAPP_BK_IAM_APIGW_NAME`，`stag="stage"`
- 日志平台：`BK_LOG_API_URL`：
    - 若 `BKAPP_LOG_API_URL` 存在，直接使用
    - 否则 `BKAPP_USE_APIGW=True` 用 APIGW `api_name`=`BKAPP_LOG_APIGW_NAME`
    - 否则用 ESB `api_name`=`BKAPP_BK_LOG_ESB_NAME`
- PaaS：`BK_PAAS_API_URL` = APIGW，`api_name`=`BKAPP_BK_PAAS_APIGW_NAME`，`stage="prod"`
- 用户管理：`USER_MANAGE_URL` = ESB，`api_name`=`BKAPP_USERMANAGE_ESB_NAME`
- BkBase：`BK_BASE_API_URL`：
    - 若 `BKAPP_BASE_API_URL` 存在，直接使用
    - 否则 APIGW `api_name`=`BKAPP_BK_BASE_APIGW_NAME`，`stag="test"`
- 监控：`BK_MONITOR_API_URL`：
    - `BKAPP_USE_APIGW=True` 用 APIGW `api_name`=`BKAPP_BK_MONITOR_APIGW_NAME`，`stag="stage"`
    - 否则用 ESB `api_name`=`BKAPP_MONITOR_V3_ESB_NAME`
- CMSI：`BK_CMSI_API_URL`：
    - 若 `BKAPP_CMSI_URL` 存在，直接使用
    - 否则 ESB `api_name`=`BKAPP_CMSI_ESB_NAME`（传入 `stage="prod"`，但 ESB 实际忽略 stage）
- 水印（DevSecOps）：`WATERMARK_API_URL` = APIGW，`api_name`=`BKAPP_DEVSECOPS_APIGW_NAME`
- 标准运维（SOps）：`BK_SOPS_API_URL` = APIGW，`api_name`=`BKAPP_BK_SOPS_APIGW_NAME`，`stag="stage"`
- ITSM：`BK_ITSM_API_URL`：
    - `BKAPP_USE_APIGW=True` 用 APIGW `api_name`=`BKAPP_BK_ITSM_APIGW_NAME`
    - 否则用 ESB `api_name`=`BKAPP_ITSM_ESB_NAME`
- Vision：`BK_VISION_API_URL`：
    - 若 `BKAPP_BK_VISION_API_URL` 存在，直接使用
    - 否则 APIGW `api_name`=`BKAPP_BK_VISION_API_NAME`，`stag="stag-new"`
- IAM V4：`BK_IAM_V4_API_URL` = APIGW，`api_name`=`BKAPP_BKIAM_APIGW_NAME`，`stag="dev"`

**示例：仅覆盖 APIGW 名称**

- 需求：在自建环境中 APIGW 名称不同，但网关域名/Stage 规则一致。
- 配置：
    - `BKAPP_BK_PAAS_APIGW_NAME=my-paas-gw`
    - `BKAPP_BK_IAM_APIGW_NAME=my-iam-gw`
    - `BKAPP_LOG_APIGW_NAME=my-log-gw`

**示例：直接指定完整 URL**

- 需求：网关域名或路径不一致，且无法通过 `api_name` 规则构造。
- 配置：
    - `BKAPP_LOG_API_URL=https://gw.example.com/api/log-search/prod/`
    - `BKAPP_BASE_API_URL=https://gw.example.com/api/bk-base/test/`

**示例：切换至 ESB**

- 需求：某些环境不开放 APIGW，使用 ESB。
- 配置：
    - `BKAPP_USE_APIGW=False`
    - 如需调整 ESB 组件名：`BKAPP_BK_LOG_ESB_NAME=my_bk_log`、`BKAPP_MONITOR_V3_ESB_NAME=my_monitor_v3`
