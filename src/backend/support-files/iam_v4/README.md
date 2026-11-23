# IAM V4 权限模型迁移

本目录维护审计的 IAM V4 系统配置、资源类型、操作、角色及其操作关系。独立命令不会修改 IAM V3、用户授权、人员、用户组或审批流程，也不会随每个实例部署自动执行。

## 部署变量

| 变量 | 用途与取值 |
| --- | --- |
| `BKAPP_BK_IAM_V4_API_URL` | 必填。目标环境的 IAM V4 网关完整地址，包含 stage，例如 `https://iam-gateway.example.com/api/bkiam/prod`。 |
| `BKAPP_IAM_SYSTEM_ID` / `BKAPP_IAM_SYSTEM_NAME` | 复用运行态系统 ID / 名称，默认 `bk-audit` / `审计中心`；ID 必须匹配模型。 |
| `BKPAAS_APP_ID` / `BKPAAS_APP_SECRET` | 已有审计应用凭据，由部署环境或 KMS 提供；模型管理需单独核对 API 授权，不使用平台用户 token。 |
| `BKAPP_IAM_V4_MODEL_CLIENTS` | 允许调用 IAM 系统的应用 appcode，逗号分隔。默认不填：首次注册只加入当前 `BKPAAS_APP_ID` 对应的 appcode，已有系统保留线上名单。显式填写时按完整名单覆盖；两种情况下都会确保当前应用在名单中。 |
| `BKAPP_IAM_V4_MODEL_MANAGERS` | 首次注册的 IAM 系统管理员账号，逗号分隔，默认为空。各环境按需填自己的管理员；更新已有系统时忽略此配置，不覆盖线上名单。 |
| `BKAPP_BK_IAM_RESOURCE_API_HOST` | IAM 可访问的审计 HTTPS 地址，例如 `https://audit.example.com`。命令自动拼接 `/api/v1/iam/resources/`；多租户用可按租户分流的共享入口。例外用 `--callback-url`。 |

单租户默认不加租户头，特殊网关可用 `--tenant-id`。多租户模型固定使用 `system`，不使用审计实例的租户 ID。两个租户共享模型，业务鉴权、授权及回调仍按目标租户处理；命令不负责部署回调路由。显式指定的迁移网关须与部署目标核对，命令不会回退到运行态默认 stage。

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
