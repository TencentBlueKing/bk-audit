# IAM V4 权限模型迁移

本目录维护审计的 IAM V4 系统配置、资源类型、操作、角色及其操作关系。独立命令不会修改 IAM V3、用户授权、人员、用户组或审批流程，也不会随每个实例部署自动执行。

## 部署变量

| 变量 | 用途与取值 |
| --- | --- |
| `BKAPP_BK_IAM_V4_API_URL` | 模型同步必填，也是运行时优先使用的 IAM V4 网关地址，包含 stage，例如 `https://iam-gateway.example.com/api/bkiam/prod`。运行时不填则多租户用 `prod`，单租户沿用原有环境规则。 |
| `BKAPP_BK_IAM_V4_SYSTEM_DETAIL_ACTION` | 运行时系统详情及回调 token 查询的相对路径，默认 `/api/v1/open/rabc/share/model/systems/{system_id}/`。如果当前 IAM 网关发布的是 `rbac`，为该环境的各审计实例设置 `/api/v1/open/rbac/share/model/systems/{system_id}/`，保留 `{system_id}` 占位符；其他环境不配。此配置不影响模型同步命令。 |
| `BKAPP_SYSTEM_TENANT_ID` | 全租户应用注册所在的租户，默认 `system`。多租户下，模型同步任务和各实例读取 IAM 回调 token 都用这个值，不填实例自己的租户 ID。同一环境只需同步一份模型。 |
| `BKAPP_IAM_SYSTEM_ID` / `BKAPP_IAM_SYSTEM_NAME` | 复用运行态系统 ID / 名称，默认 `bk-audit` / `审计中心`；ID 必须匹配模型。 |
| `BKAPP_BUILTIN_ASSET_SYSTEM_ID` | 仅定位审计本地的六类内置资产及其快照。未配置或空值沿用 `BKAPP_IAM_SYSTEM_ID`；纯 V4 新装显式填 `iam_v4_bk-audit`。不改变远端 IAM 系统 ID、鉴权或回调 token 的读取身份。 |
| `BKPAAS_APP_ID` / `BKPAAS_APP_SECRET` | 已有审计应用凭据，由部署环境或 KMS 提供；模型管理需单独核对 API 授权，不使用平台用户 token。 |
| `BKAPP_IAM_V4_MODEL_CLIENTS` | 允许调用 IAM 系统的应用 appcode，逗号分隔。默认不填：首次注册只加入当前 `BKPAAS_APP_ID` 对应的 appcode，已有系统保留线上名单。显式填写时按完整名单覆盖；两种情况下都会确保当前应用在名单中。 |
| `BKAPP_IAM_V4_MODEL_MANAGERS` | 首次注册的 IAM 系统管理员账号，逗号分隔，默认为空。各环境按需填自己的管理员；更新已有系统时忽略此配置，不覆盖线上名单。 |
| `BKAPP_BK_IAM_RESOURCE_API_HOST` | IAM 可访问的审计 HTTPS 地址，例如 `https://audit.example.com`。命令自动拼接 `/api/v1/iam/resources/`；多租户用可按租户分流的共享入口。例外用 `--callback-url`。 |

单租户默认不加租户头，模型同步遇到特殊网关可用 `--tenant-id`。多租户共享一份模型和回调 token，但业务鉴权、授权和资源查询仍在目标租户的实例处理。模型同步命令不会回退到运行时的默认网关，也不会配置回调路由。

## 执行命令

在后端部署运行目录执行，默认使用当前版本的 [model.json](model.json)。用 `--model` 可以指定另一份完整模型。

```sh
python manage.py iam_v4_migrate --dry-run  # 只查 IAM、打印差异；不加参数也是预览
python manage.py iam_v4_migrate --apply    # 读取现状后直接增、改、删或删后重建
```

`--apply` 不要求先预览。写入前会把当前和目标模型保存到 `~/.local/state/bk-audit/iam-v4-snapshots/`；可用 `--snapshot-dir` 指定已有的私有目录。无法保存快照时不会写 IAM。需要锁定某次预览时，可选传 `--expect-plan <plan_digest>`。同一网关、同一系统每次只安排一个执行者。

单次执行可以用 `--clients` 覆盖客户端环境变量，传入完整名单，不是追加。`--managers` 也可覆盖管理员环境变量，但仍只在首次注册时生效。

目标模型没有的资源类型、操作、角色和角色操作关系会被删除；不会删除整个系统，也不会级联删除授权。修改资源祖先、变更仍被角色引用的操作绑定、调整角色授权范围或出现名称冲突时，命令会报告阻塞项，整批不写入。

中途失败不会自动回滚。根据命令提示确认已完成的步骤，重新读取 IAM 后再决定是否继续。模型快照不包含已有授权。成功时命令会读回并核对模型；再次预览应看到 `changes=0`。

上线前在两租户用真实 IAM 请求验同 ID 但不同数据的 list/detail 回调，确认租户头透传、匹配实例；缺失、未知或错租户不能进入其他实例。不要把命令的 dry-run 当作回调已验收。

## 六类内置资产初始化

模型保留原有 `risk`、`strategy`，另注册根资源 `strategy_tag`、`ticket_permission`、`ticket_node`、`manual_event`，复用现有 Provider，不增加 Action、角色或授权关系。发布模型前先核对 dry-run 的差异，确认没有意外删除或授权变更；平台还需支持无 Action 资源注册及详情回读。

纯 V4 新装设置本地资产 ID 后，初始化会先检查该 ID 的本地 `System` 和六类 `ResourceType`，缺项时在资产写入前报出，请等待元数据同步或排障后重试。不要清除已有完成标记，也不要手填 RT。资产下发可能异步完成；初始化命令返回不代表六类资产已就绪，应独立回查 Snapshot/Storage。快照就绪后现有任务回填五项 RT，手工事件就绪后按原初始化入口补齐默认规则策略；已有 RT 与策略绑定不自动覆盖。

V3 存量仅升级 IAM 后端时保持原资产 ID，不设置新 ID。若原 ID 下已登记六类中任一资产快照，显式切换本地 ID 会报迁移冲突并保留原资源，本期不自动改名、迁移或重建。旧资产仍需在切换前后验证真实 PULL 的鉴权、解析及落表，不能用保留登记代替拉数验证。

多租户共享回调入口下，仅审计自身本地资产 ID 的六类资源在资产预检、Schema 和新下发的资产 PULL 中携带当前实例的 `X-Bk-Tenant-Id`。第三方资源和单租户路径不加该头；IAM 控制面读取回调 token 仍用注册租户。已有 BKBase PULL 不会因此自动更新凭据或租户头，需另行协调原配置更新与回退，并核对回调两侧 token 匹配状态，勿输出 token 值。
