# BKBase V4 正式发布只读证据校验

这组工具用于 **BKBase 已迁移、审计新代码尚未发布** 时的离线预检，以及 **审计正常部署/schema 自动迁移、完成本地数据迁移之后** 的配置对账。它读取旧 schema 的原生 fixture，不导入候选 Django model、不连接平台、不执行 migrate、不提供 apply 或自动修复。

`PASS` 只表示给定证据的自动检查通过。当前有限实现对字段/规则语义、复杂 Flow 能力与输出物理存储、完整快照/IAM契约明确输出 `NOT_CHECKED`；有迁移对象的正常报告通常是 `NOT_CHECKED`，须由负责人补充人工证据，**不能作为自动放行**。`FAIL` 和 `NOT_CHECKED` 都退出 1，报告创建失败退出 2；不要用 `|| true` 隐藏结果。报告包含对象身份摘要及错误代码，不回显配置、SQL、规则、连接、原始响应或凭据。

完整顺序沿正式发布清单：固定目标和版本 → 数据库/业务备份与恢复核验 → 本工具 preflight → 正常 Helm 部署及自动 schema migrate → 既有审计本地迁移 → 本工具 postflight → 必要初始化及人工产品验收。数据库备份仍用 [已有工具](../database/README.md)，本组配置导出不是整库备份或恢复验证。已有迁移命令的 dry-run 依赖新 schema，不能替代发布前步骤。

## 1. 固定环境、来源及版本

在受控私有目录保存 `context.json`。下方全是示例，应逐项替换成发布单与实际配置；跨项目资源应明确列出该环境允许的 namespace，不从旧项目号、业务号或资源名推导。

```json
{
  "environment": "formal-a",
  "application": "audit-app",
  "database": {"host": "actual-db", "port": "3306", "name": "actual_audit_db"},
  "source": {"tenant": "actual-legacy-environment", "project_id": 18},
  "source_version": "actual-old-backend-build",
  "release_version": "actual-candidate-backend-build",
  "tenant": "actual-v4-tenant",
  "namespaces": ["actual-default-project", "actual-migrated-project"],
  "api_origin": "https://actual-api-gateway.example/stage",
  "max_baseline_age_seconds": 604800,
  "max_evidence_age_seconds": 14400
}
```

`api_origin` 是真实 API base URL（可包含网关前缀），不允许用户信息、查询参数或 fragment。旧 tenant 是明确的旧来源范围标识，工具不会向 V3 查询其真实性；旧项目号必须为正整数。context 的本地 SHA 同时写入导出 manifest 和校验报告，以识别使用了哪份声明。

迁移前 `before` 的有效期取 `max_baseline_age_seconds`，未设置时沿用 `max_evidence_age_seconds`。V4 GET、部署回执和 `after` 仍使用 `max_evidence_age_seconds`。在首次导出前按发布窗口确定上下文。

另存独立的 `deployment-before.json`/`deployment-after.json`：从发布平台、Helm 工作负载或容器实际镜像回读得到，不要把 context 的候选值直接复制后称已核实。工具只验证给定回读与声明的一致性、镜像 digest 格式及采集时间，**无法认证回读来源或证明正在运行该版本**，manifest 中 `deployed_version_authenticity=NOT_CHECKED`。

```json
{
  "environment": "formal-a",
  "application": "audit-app",
  "stage": "before",
  "version": "actual-old-backend-build",
  "image_digest": "sha256:替换为实际64位小写十六进制digest",
  "collected_at": "2026-11-17T20:00:00+08:00",
  "source": "实际部署回读来源、发布单或证据文件标识"
}
```

后置使用 `stage=after` 和实际已部署候选版本。不要使用 `settings.VERSION`：本项目没有可靠的应用构建版本设置。

## 2. 从目标已部署代码只读导出配置

将本目录两个 Python 文件作为独立工具复制到目标受控目录；发布前仍从 **当前已部署旧审计代码/旧环境** 的 `.venv` 启动 `manage.py shell`。不要将候选新 model 装入旧服务；这里依赖的是目标已安装的旧 Django model 元数据。后置再从已部署的新代码运行相同入口。本轮没有在真实服务执行这些命令。

```bash
AUDIT_RELEASE_CONTEXT=/private/release/context.json \
AUDIT_DEPLOYMENT_EVIDENCE=/private/release/deployment-before.json \
AUDIT_EXPORT_STAGE=before \
AUDIT_RELEASE_EXPORT_DIR=/private/release/before-new-directory \
.venv/bin/python manage.py shell -c \
'import runpy; runpy.run_path("/private/tools/bkbase_v4/export_fixture.py", run_name="__main__")'
```

目标父目录须已存在且私有；输出目录须不存在。入口核 `APP_CODE`、连接配置及 `SELECT DATABASE()` 的真实库名。旧 `BKBASE_PROJECT_ID` 的规范数字字符串和正整数均可，拒绝 bool、前导零和非法文本。读取选定已部署配置模型及其自动 M2M 表的引擎，拒绝非 InnoDB；在同一 `REPEATABLE READ / READ ONLY` 事务内取得各模型行数和原生 `dumpdata --all` 内容，包含软删除；最终 `ROLLBACK`，之后才在本机新建文件。

输出 `business.json` 和 `manifest.json`，文件 0600、目录 0700，独占创建不覆盖。**原生业务 fixture 是私有配置快照，可能含敏感配置，必须留在受控位置，不粘贴到聊天、工单或公开仓库**；校验报告只输出白名单摘要。导出范围沿已有业务导出：meta/databus/strategy_v2 的已管理配置模型，排除 storage 操作日志、snapshot statistic、策略/联表审计日志及 tag sync trash；不包含风险明细、数据库结构或其他应用。

这是“指定配置模型同一 DB 快照的行数与内容一致”，不是整库完整性。既有 `business.json + manifest.json` 包也可直接作为输入；`read_bundle` 沿原格式核完成标记、字节 SHA、每模型行数、模型/主键唯一性。旧包没有版本/旧来源证据时报告 `NOT_CHECKED`，不要改写原始 manifest 补造证明。`01_inventory.py` 的精简库存可帮助人工分范围，但缺少完整保留字段，不能单独充当本工具基线。旧 `export_business_backup.py` 的 export 分支硬编码了 BKOP，正式环境不要照跑它。

后置替换上述三个位置：`deployment-after.json`、`AUDIT_EXPORT_STAGE=after`、全新的 after 目录。实际 schema 沿正常部署自动 migrate，不通过本工具变更。

## 3. 复用正式清单，覆盖整份库存

`plan.json` 是只读核验的范围封套，`context` 原样放固定声明，`objects` 对输入 fixture 的**每条配置记录**列一次：需要迁移的写 `action=migrate`；无关、删除、无 Flow 等对象写 `action=exclude` 并说明 `reason`。排除仍会参加后置保留字段比较。遗漏、重复、未知对象都失败。不要默认将所有未识别对象排除。

发布需要新增或修改两项 V4 运行配置时，在顶层 `approved_config_changes` 按 `instance_key`、`config_key`、`config_value` 填入签收后的完整目标值。仅支持审计 namespace 下的 `bkbase_v4_storage_clusters` 和 `bkbase_v4_flow_config`。后置校验逐项核对目标值，已有记录继续校验主键和保留字段，新建按相同配置键和审计 namespace 定位。

结构合法的空库存/空计划，或全部为 `exclude` 的清单，没有任何迁移对象得到核验，预检及后置均报告 `NO_MIGRATION_OBJECTS: NOT_CHECKED`，CLI 退出 1。非空库存被空计划遗漏、重复或非法输入仍是 `FAIL`；正常混合清单保留原迁移及保留字段检查。这是自动检查范围缺项，不要求启动原停用资源，也不增加排除审批或把人工确认改写为自动通过。

可离线生成待审核骨架（从后端目录执行；这只创建本机文件）：

```python
import runpy
c = runpy.run_path("support-files/bkbase_v4/release_checks.py")
context = c["read_json"]("/private/release/context.json")
before = c["read_bundle"]("/private/release/before-new-directory")
plan = {"schema_version": 1, "context": context, "objects": [
    {"model": r["model"], "pk": r["pk"], "action": "review_required"}
    for r in before["rows"]
]}
c["write_private"]("/private/release/plan-review-required.json", plan)
```

Flow 对象形状如下；`mapping` **原样使用**既有 `flow_migration` schema_version=1 详细清单的单行，`source` 取其同份 source；当前简版 `flow_id -> name` 清单不含明确旧业务输出，须先依据真实旧配置/正式明细补齐，脚本不会猜。`expected_state` 对旧 running 为 running、旧 disabled 为 stopped；其他在途/失败状态不自动通过。

```json
{
  "model": "strategy_v2.strategy", "pk": 7, "action": "migrate", "scenario": "flow",
  "source": {"tenant": "actual-legacy-environment", "project_id": 18},
  "expected_state": "stopped",
  "mapping": {
    "strategy_id": 7, "audit_namespace": "actual-audit-namespace", "legacy_flow_id": 41,
    "flow": {"kind": "Flow", "tenant": "actual-v4-tenant", "namespace": "actual-migrated-project", "name": "actual-flow"},
    "output_rt_id": "22_actual_output", "migration_status": "succeeded"
  },
  "checks": []
}
```

普通/事件插件及采集项分别用 `scenario=plugin/event_plugin/collector`；`model` 分别为 `databus.collectorplugin/collectorconfig`。`mapping` 原样取已有 `resource_migration` 详细清单单行（owner/owner_pk/audit_namespace/legacy/data_source〔可选〕/data_id/clean/result_table/storages）。保留旧字段、节点 ID；不会改 Ref、补建资源或推断类型。事件插件必须是本地 `plugin_scene=event`、唯一主 Doris，并核既有 namespace 级事件 GlobalMeta 逻辑表/物理目标；普通插件沿主 ES、副 Doris 标记；采集项不认领父插件 Storage。

快照/IAM 可做有限身份及后置绑定对账。`scenario=snapshot` 使用明确旧 `legacy` 和实际所需的 Redis、HDFS、Doris 存储，`mapping.storages` 每项填 `{resource, cluster}`。`expected_binding` 填 `raw_data_id`、`data_source`、`data_id`、`clean`、`clean_role`、`result_table_id`、`result_table`、`storages`，存储值为 DataStorage Ref。`scenario=iam` 使用现有 IAM 绑定形状（`source_raw_data_id` 和 Redis 绑定），另提供 `config_key` 和 `binding_namespace`，在 `config_value.bkbase_v4[tenant][namespace]` 核对。两类仍需要人工签收完整契约。

`checks` 仅作额外字面比较：`topic=fields` 的 `/spec/fields` 或原生 Flow `/spec/nodes/<index>/fields`；`topic=rules` 的 Clean `/spec/rules`、StreamNode `/spec/nodes/<index>/config/sql`、BatchSqlNode `/spec/nodes/<index>/processing_info`；提供 `ref`、`pointer` 和 `equals` 或 `sha256` 二选一。Ref 必须是当前对象的主 Flow/Clean/RT 或实际 Flow 源/输出 RT，禁止 decoy 资源替代；不能为空。主身份、旧输入/输出、任务关联和存储用途由内置逻辑校验，不接受自选 pointer 充数。即使字面比较相同，**V3/V4字段类型/规则语义等价仍 NOT_CHECKED**，需人工依据旧规则和正式模型补查。

## 4. 收集精确只读 GET 回执

由实际授权环境/API 工具执行精确 GET，保全真实 URL、HTTP状态、带时区采集时间和完整响应。工具本身不发送 HTTP，也不接收凭据。将原始响应放本地私有文件，按以下结构封装；包装时使用原始采集时间，不用当前时间伪装新鲜度。

```json
{
  "schema_version": 1, "context": {"与context.json完全相同": "此处仅示意"},
  "items": [{
    "ref": {"kind": "Flow", "tenant": "actual-v4-tenant", "namespace": "actual-migrated-project", "name": "actual-flow"},
    "method": "GET", "operation": "resource_get",
    "url": "https://actual-api-gateway.example/stage/v4/tenants/actual-v4-tenant/namespaces/actual-migrated-project/flows/actual-flow/",
    "http_status": 200, "collected_at": "2026-11-17T20:00:00+08:00",
    "body": {"实际完整响应": "此处仅示意"}, "body_sha256": "canonical JSON SHA256"
  }]
}
```

规范 SHA 用 `release_checks.py` 的 `digest(item["body"])`，然后 `write_private(new_path, receipts)`；不要 hash 格式化后的文件字节。该 SHA 只检完整性，**不是真实性签名**。回执不能仅凭 SHA 通过，还要实际解析成功包裹、严格身份、源/RT/Storage等内容与正式清单比较。

固定路径沿项目 API：

| kind/operation | api_origin 后的精确路径 |
| --- | --- |
| Flow | `/v4/tenants/{tenant}/namespaces/{namespace}/flows/{name}/` |
| DataSource | `/v4/tenants/{tenant}/namespaces/{namespace}/datasources/{name}/` |
| Clean | `/v4/tenants/{tenant}/namespaces/{namespace}/cleans/{name}/` |
| DataStorage | `/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/{name}/` |
| DataId | `/v4/namespaces/{namespace}/dataids/{name}/` |
| ResultTable | `/v4/namespaces/{namespace}/resulttables/{name}/` |
| ResultTable、operation=result_table_info | `/v4/result_tables/{logical_id}/`，item 另给 `logical_id` |

ResultTableInfo 与原生 ResultTable 可分别保留各一份；所用 Ref 仍须对应响应 metadata 的 tenant/namespace/name。缺 GET、缺状态/逻辑身份/版本/范围、无对应断言报 `NOT_CHECKED`；错 HTTP、错误 API code、错路径/租户/身份、过期或未来时间、重复回执报 `FAIL`。缺资源不当不存在后自动创建。DataStorage `phase=Ok` 只表示配置生效，不解释为任务运行或非空；元数据缺 `physical_table_name` 不直接判失败，原配置/正式清单的目标仍用于后置存储目标对账（C30）。不从 `spec.bizId` 猜旧业务身份。

## 5. 运行及解读

在独立当前工具环境从后端目录运行，只需 Python 标准库：

```bash
.venv/bin/python support-files/bkbase_v4/release_checks.py preflight \
  --context /private/release/context.json --plan /private/release/plan.json \
  --before /private/release/before-new-directory --receipts /private/release/receipts-before.json \
  --output /private/release/preflight-new.json
```

正常部署及本地迁移之后，重新采集实际本地配置与必要正式 GET，运行：

```bash
.venv/bin/python support-files/bkbase_v4/release_checks.py postflight \
  --context /private/release/context.json --plan /private/release/plan.json \
  --before /private/release/before-new-directory --after /private/release/after-new-directory \
  --receipts /private/release/receipts-after.json --output /private/release/postflight-new.json
```

后置逐对象核**实际**保存的 Ref、tenant、namespace、输出、存储用途及已声明物理目标；compare 整份前后配置，仅允许明确绑定叶子和导入会清除的 ready/clean_ready 变化，旧 backend_data、节点 ID、停用态、V3字段和无关配置变化报 `PRESERVATION`。不使用 apply 日志或 ready 布尔替代配置。未知新增/缺失记录严格报 `POST_SCOPE`；有意新增配置行、其他版本新增非绑定字段等超出当前比较能力，应单独人工核验并保全证据，不能原地重写基线掩盖差异。报告对象摘要可用 `digest([model, pk])[:16]` 在私有库存定位。

当前自动结果与人工项须分别记录：自动 `FAIL` 先定位处理；自动 `NOT_CHECKED` 不等于已批准忽略。脚本不提供把未知一键转 PASS 的参数。

## 6. 尚需正式人工补查

- 确认部署/GET回读确实来自实际目标，现场版本/镜像及配置加载正确；离线自校验不能证明该事实。
- 数据库endpoint、DNS/VIP实际指向须与发布单、部署配置及备份manifest的服务身份人工交叉核对；工具不能自动排除同名库/别名误连，不以文件自洽替代真实目标确认。
- 对旧字段类型、Clean规则/SQL语义和时间精度做旧配置→平台正式模型比较；Flow实时/离线/关联资产的 Channel/Redis/Hdfs Binding 能力、维表语义、输出主副存储及物理目标逐场景补核。
- IAM 的完整只读观察入口是 `services.web.databus.collector.snapshot.system.v4._observe_binding(resource_type, context, normalized_binding)`；参数从现存 `_read_config/_scoped_binding/_normalize_binding` 取得，仅输出摘要。它核 PULL/report_config、Redis Join key、Storage及 RedisBinding。**不要调用** `ensure_system_snapshot`、`_start_verification` 或 apply 入口来充当只读核验，它们会写本地状态。发布前如旧运行代码无 V4 模块，仍用正式 GET 回执人工按该契约核；发布后可在新代码中做该只读观察。
- 普通/Basic快照的既有只读关系核验参考 `snapshot_restore._read(..., configure_source=False)`、`source._replay_preflight(..., configure=False)`；它们是需要完整合法参数的内部函数，适用于对应场景，后者要求正在运行的来源，不能拿它要求原关闭对象启动。受控人工按实际参数核 DataConn/PULL、角色、连接与上下游，不调用 prepare/advance/start/replay 等写路径，也不输出这些函数返回的连接或配置正文。
- IAM/资产的 Redis非空、刷新/增量、必要权限/连通性，以及完整插件/事件/策略/风险/通知产品链路仍做正式人工验收。不会从资源200、phase Ok、旧历史读取或进程 ready 推出新数据链通过。

## 离线验证与本地交接

```bash
.venv/bin/python -m unittest discover -s support-files/bkbase_v4/tests -v
```

测试使用合成脱敏原生结构及假 DB 边界，不运行 Django setup、真实DB/Redis/HTTP/socket。当前阶段记录见 [阶段交回](../../debug/开发方案/BKBaseV4升级评估/bkop-v4迁移/execution/正式发布预检与后置校验-20261117/scripts/阶段交回.md)。私有正式输入与报告放忽略目录，不放本目录；本目录只收脚本、说明与隔离测试。
