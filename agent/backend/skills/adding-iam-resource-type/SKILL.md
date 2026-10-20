---
name: adding-iam-resource-type
description: Use when adding a new IAM resource type to bk-audit, registering resource providers, creating IAM migrations, or encountering ResourceNotRegistered errors for new resource types
---

# 新增 IAM 资源类型

## Overview

在蓝鲸审计中心新增 IAM 资源类型的实现清单，覆盖类型定义、注册、provider 与 IAM 同步；资产同步、实例选择和操作定义按资源需求决定。

以下文件路径相对于产品 checkout 的 src/backend，不是技能安装目录。

## When to Use

- 需要新增一种受 IAM 管控的资源类型（如 TicketNode、LinkTable）
- 需要为新资源注册反向拉取 provider
- 遇到 `ResourceNotRegistered` 或 `ResourceNotExistError` 错误
- 需要将新资源纳入 BkBase 资产同步

**不适用于：** 仅修改已有资源类型的属性或操作

## Quick Reference

| 步骤 | 文件 | 说明 |
|------|------|------|
| 1 | `apps/permission/handlers/resource_types/{module}.py` | 定义 `ResourceTypeMeta` 子类 |
| 2 | `apps/permission/handlers/resource_types/__init__.py` | 注册到 `ResourceEnum` |
| 3 | 对应模块下 `provider.py` | 实现 `IAMResourceProvider` |
| 4 | `apps/permission/urls.py` | 注册 provider URL |
| 5 | `support-files/iam/initial.json` | 添加 `upsert_resource_type` |
| 6 | `apps/permission/migrations/` | 新建 migration 执行 IAM 同步 |
| 7 | （可选）资产同步相关 | `init_asset`、`sync_asset_bkbase_rt_ids`、constants |

## 步骤详解

### 1. 定义资源类型

在 `apps/permission/handlers/resource_types/` 下对应模块文件中新增类：

```python
class TicketNode(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "ticket_node"
    name = gettext("风险处理记录")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": id}]
```

**要点：**
- `id` 必须全局唯一，使用 snake_case
- `related_instance_selections` 中的 `id` 通常与资源类型 `id` 一致
- 如需实例名称展示，覆写 `create_instance` 类方法

### 2. 注册到 ResourceEnum

在 `apps/permission/handlers/resource_types/__init__.py` 中：

```python
from apps.permission.handlers.resource_types.risk import TicketNode

class ResourceEnum:
    ...
    TICKET_NODE = TicketNode
```

### 3. 实现 Resource Provider

在对应模块的 `provider.py` 中实现 provider 类。先阅读 `apps/permission/provider/base.py` 和相邻资源的实现；这里的两种基类均由项目定义，继承 IAM SDK 的 `ResourceProvider`：

- `BaseResourceProvider`：轻量封装，默认返回空的属性列表与属性值；实例相关接口由子类按 SDK 协议实现。
- `IAMResourceProvider`：提供实例列表、详情、搜索及资源 schema 等通用处理，子类补充过滤逻辑和序列化定义；也可按需支持静态快照/资产同步。现有 `TicketNodeResourceProvider` 使用这个基类。

当前锁定依赖 `bk-iam==1.3.2` 的 `ResourceProvider` 还将 `list_instance_by_policy` 声明为抽象方法，项目 `IAMResourceProvider` 未替它实现。具体 provider 必须同时补齐本类及 SDK 继承的抽象成员，否则无法实例化；升级依赖时重新核对该契约。

**IAMResourceProvider 的实现与扩展点：**

| 成员 | 用途与要求 |
|------|------|
| `resource_provider_serializer` | 必需的序列化器定义，可按资源能力返回 `None` |
| `list_attr_value_choices` | 必须实现的属性值查询 |
| `filter_list_instance_results` | 必须实现的实例列表过滤 |
| `filter_fetch_instance_results` | 必须实现的实例详情过滤 |
| `filter_search_instance_results` | 必须实现的搜索过滤 |
| `fetch_instance_list` | 按需实现静态快照/资产同步拉取，关注分页性能 |
| `list_instance_by_policy` | 必须实现的策略实例列举；继承的 SDK 抽象方法 |

策略实例列举可参考 `services/web/risk/provider.py` 的 `TicketNodeResourceProvider`。下面摘录其关键方法，其余抽象成员仍需按上表实现：

```python
def list_instance_by_policy(self, filters, page, **options):
    expression = filters.expression
    if not expression:
        return ListResult(results=[], count=0)

    key_mapping = {f"{self.resource_type}.id": "id"}
    converter = PathEqDjangoQuerySetConverter(key_mapping)
    django_filters = converter.convert(expression)
    queryset = TicketNode.objects.filter(django_filters)
    results = [
        {"id": str(item.pk), "display_name": str(item.pk)} for item in queryset[page.slice_from : page.slice_to]
    ]
    return ListResult(results=results, count=queryset.count())
```

**`fetch_instance_list` 分页 — 偏移切片与延迟关联：**

下面示例先按时间排序并用偏移切片取得 PK，再按 PK 回表读取数据。延迟关联减少第一阶段读取的字段；深偏移成本和索引使用仍需结合实际数据与执行计划验证：

```python
def fetch_instance_list(self, filter, page, **options):
    start_ts = float(filter.start_time) / 1000.0
    end_ts = float(filter.end_time) / 1000.0
    base_qs = Model.objects.filter(timestamp__gt=start_ts, timestamp__lte=end_ts)
    # 第一阶段只查询 PK
    pk_list = list(
        base_qs.order_by("timestamp")
        .values_list("id", flat=True)[page.slice_from : page.slice_to]
    )
    # 再用 PK 回表取完整数据
    queryset = Model.objects.filter(pk__in=pk_list).order_by("timestamp")
    ...
```

### 4. 注册 Provider URL

在 `apps/permission/urls.py` 中：

```python
from services.web.risk.provider import TicketNodeResourceProvider

if TicketNodeResourceProvider is not None:
    resources_dispatcher.register(ResourceEnum.TICKET_NODE.id, TicketNodeResourceProvider())
```

**注意：** 使用 `if ... is not None` 防御性导入，避免服务模块未加载时报错。

### 5. 修改 IAM 迁移定义文件

在 `support-files/iam/initial.json` 中添加 `upsert_resource_type` 操作：

```json
{
  "operation": "upsert_resource_type",
  "data": {
    "id": "ticket_node",
    "name": "风险处理记录",
    "name_en": "Ticket Node",
    "description": "",
    "description_en": "",
    "parents": [],
    "provider_config": {
      "path": "/api/v1/iam/resources/"
    },
    "version": 1
  }
}
```

**按需添加（仅当资源需要在 IAM 界面被选择时）：**
- `upsert_instance_selection` — 实例视图(用于定义资源在 IAM 中被拉取的视图)
- `upsert_action` — 操作定义
- `upsert_action_groups` — 操作分组（覆盖式更新，必须包含所有操作）

### 6. 创建 Django Migration

新建迁移前，检查当前分支 `apps/permission/migrations/` 的依赖图并确认叶节点；存在分叉时先按项目约定处理合并依赖，不只按文件编号判断。

下面的 `<permission-leaf-migration>` 是占位名称，必须替换为当前依赖图中选定的上游迁移名；不能直接复制历史示例的依赖。随后在该目录创建新迁移文件：

```python
import os
from django.db import migrations
from iam.contrib.iam_migration.migrator import IAMMigrator
from core.utils.distutils import strtobool

def forward_func(apps, schema_editor):
    if strtobool(os.getenv("BKAPP_SKIP_IAM_MIGRATION", "False")):
        return
    migrator = IAMMigrator(Migration.migration_json)
    migrator.migrate()

class Migration(migrations.Migration):
    migration_json = "initial.json"
    dependencies = [
        ("permission", "<permission-leaf-migration>"),  # 替换为当前图选定的实际依赖
    ]
    operations = [migrations.RunPython(forward_func)]
```

### 7. （可选）资产同步

如果资源需要同步到 BkBase，还需修改：

| 文件 | 修改 |
|------|------|
| `services/web/databus/constants.py` | 新增 `ASSET_XXX_BKBASE_RT_ID_KEY` 常量 |
| `services/web/entry/init/base.py` | `init_asset` 的 `assets` 字典中添加资源 |
| `services/web/databus/tasks.py` | `sync_asset_bkbase_rt_ids` 的 `asset_configs` 中添加映射 |
| 使用 BkBase 查询的 resource | `_get_bkbase_table_map` 中添加表名映射 |

## Common Mistakes

| 错误 | 症状 | 修复 |
|------|------|------|
| 漏了 `initial.json` | 部署后 IAM 不识别资源类型 | 补充 `upsert_resource_type` + 新建 migration |
| 漏了 Django migration | `initial.json` 改了但不会被执行 | 创建 `RunPython(forward_func)` 迁移 |
| 漏了 `urls.py` 注册 | IAM 回调 404 | 在 `resources_dispatcher.register` 中注册 |
| Provider 类名与 Resource 类名冲突 | `bk_resource` 自动发现报 `ResourceNotRegistered` | Handler/Provider 类名避免与 `bk_resource` 注册的 Resource 类名相同 |
| `fetch_instance_list` 查询成本过高 | 大批量或深偏移同步超时 | 检查过滤/排序索引与执行计划，衡量偏移成本；按需采用先取 PK 再回表等优化，并验证实际效果 |
| 资产同步缺少表映射 | BkBase 查询时 SQL 中保留原始 MySQL 表名，查询失败 | `_get_bkbase_table_map` 中补充映射 |

## Checklist

新增 IAM 资源类型时逐项检查：

- [ ] `ResourceTypeMeta` 子类已定义
- [ ] `ResourceEnum` 已注册
- [ ] Provider 已实现并注册到 `urls.py`
- [ ] `initial.json` 已添加 `upsert_resource_type`
- [ ] Django migration 已创建
- [ ] （如需）资产同步常量、init_asset、sync_task、table_map 已更新
- [ ] 单测覆盖 provider 各方法
