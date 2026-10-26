# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from typing import Dict

from bk_resource import api, resource
from bk_resource.exceptions import APIRequestError
from django.conf import settings

from apps.itsm.constants import ITSM_V4_MIGRATION_MAP_KEY, ITSM_V4_SYSTEM_ID_KEY
from apps.itsm.utils import V3_FIELD_TYPE_TO_JSONSCHEMA_TYPE
from apps.meta.constants import GLOBAL_CONFIG_LEVEL_INSTANCE, ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.databus.collector.snapshot.system.clean import PullCleanHandler
from services.web.databus.collector.snapshot.system.pull import HttpPullHandler
from services.web.databus.collector.snapshot.system.storage import PullStorageHandler
from services.web.databus.constants import (
    ACTION_DATA_CONFIG_KEY,
    ACTION_DATA_RT_KEY,
    RESOURCE_TYPE_DATA_CONFIG_KEY,
    RESOURCE_TYPE_DATA_RT_KEY,
    USER_INFO_DATA_CONFIG_KEY,
    USER_INFO_DATA_RT_KEY,
)

# V4 流程表单 Schema
from services.web.risk.models import ProcessApplication

# ITSM V4 接入系统（城运系统）信息
ITSM_V4_SYSTEM_NAME = settings.ITSM_SYSTEM_NAME  # 系统名
ITSM_V4_SYSTEM_CODE = settings.ITSM_SYSTEM_CODE  # system_id
ITSM_V4_SYSTEM_DESC = settings.ITSM_SYSTEM_DESC  # 系统描述

# ITSM V4 系统流程信息
ITSM_V4_WORKFLOW_PORTAL_ID = settings.ITSM_WORKFLOW_PORTAL_ID  # DEFAULT
ITSM_V4_WORKFLOW_APP_ID = settings.ITSM_WORKFLOW_APP_ID  # core
ITSM_V4_WORKFLOW_WORKING_MODE = settings.ITSM_WORKFLOW_WORKING_MODE
ITSM_V4_WORKFLOW_OPERATOR = settings.ITSM_WORKFLOW_OPERATOR  # admin


def v3_field_to_jsonschema(field):
    v3_type = (field.get("type") or "STRING").upper()
    # 单选/下拉：带 enum 约束（⚠️ ITSM V4 是否据此渲染下拉待确认）
    if v3_type in ("SELECT", "RADIO"):
        choices = field.get("choice") or []
        return {
            "title": field["name"],
            "type": "string",
            "enum": [c.get("key") or c.get("name") for c in choices if isinstance(c, dict)],
        }
    # 多选 / 复选
    if v3_type in ("MULTISELECT", "CHECKBOX"):
        return {"title": field["name"], "type": "array", "items": {"type": "string"}}
    # 多选人员：array + items.format=user（SDK 文档「多选用户」）
    if v3_type == "MEMBERS":
        return {"title": field["name"], "type": "array", "items": {"type": "string", "format": "user"}}
    # 富文本：format 大小写敏感，文档为 richText（T 大写）
    if v3_type == "RICHTEXT":
        return {"title": field["name"], "type": "string", "format": "richText"}
    # 多行文本
    if v3_type == "TEXT":
        return {"title": field["name"], "type": "string", "format": "textarea"}
    # 日期 / 日期时间
    if v3_type == "DATE":
        return {"title": field["name"], "type": "string", "format": "date"}
    if v3_type == "DATETIME":
        return {"title": field["name"], "type": "string", "format": "date-time"}
    # 时间间隔：按 SDK 文档构造 object + dateRange
    if v3_type == "DATETIMERANGE":
        return {
            "title": field["name"],
            "type": "object",
            "format": "dateRange",
            "properties": {
                "start": {"type": "string", "format": "date-time"},
                "end": {"type": "string", "format": "date-time"},
            },
            "required": ["start", "end"],
        }
    # 表格 / 自定义表格：array + format=table（列信息 V3 未承载，properties 无法还原）
    if v3_type in ("TABLE", "CUSTOMTABLE"):
        return {"title": field["name"], "type": "array", "format": "table", "properties": {}}
    # 其余：纯类型映射，缺省 string
    return {"title": field["name"], "type": V3_FIELD_TYPE_TO_JSONSCHEMA_TYPE.get(v3_type, "string")}


def init_itsm_v4():
    """
    ITSM V4 系统初始化：为每个历史处理套餐创建独立的 V4 系统流程，并把套餐的
    approve_service_id 由 V3 service_id 改写为各自对应的 V4 workflow_key。

    在部署脚本 `python manage.py init_system` 中执行（每次部署触发一次）：
    - approve_service_id 为空 => 未选择套餐，跳过，不处理；
    - resource.itsm.get_service_detail 查询失败（服务不存在/接口异常）=> 跳过该套餐，保留原 V3 id，由人工手动创建对应系统流程后再迁移，避免用不适用系统流程代替；
    - 先按 V3 approve_service_id 去重再遍历，同一 V3 服务只解析一次、只创建一个 V4 流程；
    - 流程名默认沿用 V3 原名；仅当该名字已被「其它」V3 服务认领时才加 #V3 服务标识后缀；
    - 跨轮幂等由持久化的「V3 服务 -> V4 流程」映射保证：本地已记录的直接复用，
      未记录的按本地归属关系决定名称，与远端返回内容、遍历顺序、历史状态均无关。
    """
    objs = ProcessApplication.objects.all()
    # 默认套餐（当 V3 get_service_detail 无数据时兜底使用）
    default_workflow_name = "审计中心风险处理审批流程"
    default_workflow_desc = "审计中心（bk-audit）风险自动处理审批"
    properties_base = {
        "ticket__title": {"title": "标题", "type": "string"},
        "risk_id": {"title": "风险ID", "type": "string"},
        "raw_event_id": {"title": "原始事件ID", "type": "string"},
        "event_content": {"title": "风险描述", "type": "string", "format": "textarea"},
        "tags": {"title": "标签", "type": "string"},
        "operator": {"title": "责任人", "type": "string"},
        "risk_level": {"title": "风险等级", "type": "string"},
        "process_application_name": {"title": "处理套餐名称", "type": "string"},
        "description": {"title": "说明", "type": "string", "format": "textarea"},
        "risk_url": {"title": "审计关联单据", "type": "string"},
    }

    # 传给 init_itsm_system 的 name -> key 缓存（其内部按 name 去重/复用）
    name_cache = _fetch_existing_v4_keys()

    # 创建失败的记录合集（参数/字段等），存在时不标记整体完成
    create_error = {}
    # 本轮未迁移记录（V3 详情查询失败：临时超时/网络抖动/服务下架/查不到等）
    pending_retry = []

    # 持久化的迁移映射：V3 approve_service_id -> V4 workflow_key。
    # 跨轮可恢复，任何重试都解析到同一个远端流程，不依赖远端状态和遍历顺序。
    migration_map = _load_itsm_v4_migration_map()
    # 反向索引：已被某个 V3 服务认领的 workflow_key，用于判断同名流程的归属
    claimed_keys = {key: v3_id for v3_id, key in migration_map.items()}

    # 预先拉取 V4 已有流程 key：用于识别「已迁移」套餐，避免把 V4 key 再送回 V3 查询。
    # 合并本地映射中的 key：远端拉取失败（返回 {}）或分页漏查时仍能识别已迁移套餐。
    existing_v4_keys = set(name_cache.values()) | set(migration_map.values())

    # 按 V3 approve_service_id 聚合（去重）：同一 V3 服务只解析一次详情、只创建一个 V4 流程
    pending_objs = {}
    for obj in objs:
        # 未选择套餐：无需绑定任何 V4 流程，跳过
        if not obj.approve_service_id:
            continue

        # 已迁移：approve_service_id 已经是 V4 workflow_key（存在于 V4 系统），
        # 直接跳过，绝不送回 V3 查询，否则触发 V3「查找对象不存在」报错/无效调用
        if obj.approve_service_id in existing_v4_keys:
            continue

        pending_objs.setdefault(obj.approve_service_id, []).append(obj)

    created_any = False
    for v3_service_id, related_objs in pending_objs.items():
        v3_id = str(v3_service_id)

        # 本地已记录过该 V3 服务 => 直接复用，不再解析名称、不再创建
        if v3_id in migration_map:
            _bind_process_applications(related_objs, migration_map[v3_id], v3_service_id, v3_id, create_error)
            created_any = True
            continue

        # 取 V3 服务详情，用于按套餐定制流程 name/desc
        try:
            service_info = resource.itsm.get_service_detail(id=v3_service_id, version="v3")
        except Exception as e:
            # V3 详情查询失败（临时超时/网络抖动/服务下架/查不到等）
            pending_retry.append(v3_service_id)
            print(
                "request service detail error (unfinished, retry next init_system): {},"
                " approve_service_id is: {}".format(str(e), v3_service_id)
            )
            continue

        workflow_name = default_workflow_name
        workflow_desc = default_workflow_desc
        properties = properties_base

        if service_info:
            workflow_name = service_info.get("name") or default_workflow_name
            workflow_desc = service_info.get("desc") or default_workflow_desc
            # 仅在需要新建/复用流程时解析表单字段
            fields = service_info.get("fields") or []
            if fields:
                properties = {}
                for field in fields:
                    key = "ticket__{}".format(field["key"]) if field["key"] == "title" else field["key"]
                    properties[key] = v3_field_to_jsonschema(field)

        # 名称决策：默认沿用 V3 原名；
        # 仅当该名字对应的流程已被「其它」V3 服务认领时，才加 #V3 服务标识后缀强制独立，
        # 绕开 ITSM_v4 name 唯一约束且不错绑同名服务。后缀用 v3_id（approve_service_id）：
        itsm_name = workflow_name
        existing_key = name_cache.get(workflow_name)
        if existing_key:
            owner = claimed_keys.get(existing_key)
            if owner is not None and owner != v3_id:
                itsm_name = "{}#{}".format(workflow_name, v3_id)

        form_schema = {
            "type": "object",
            "required": ["ticket__title"],
            "properties": properties,
        }
        try:
            workflow_key = init_itsm_system(form_schema, itsm_name, workflow_desc, name_cache)
        except Exception as e:
            create_error[str(v3_service_id)] = itsm_name
            print(str(e))
            continue

        # 记录归属并立即持久化：后续重试（含本地 save 失败）都解析到同一个流程
        migration_map[v3_id] = workflow_key
        claimed_keys[workflow_key] = v3_id
        try:
            _save_itsm_v4_migration_map(migration_map)
        except Exception as e:
            # 映射未落盘不阻断本轮绑定：下一轮按名称仍会复用同一个 workflow_key，幂等成立。
            # 但必须记为未完成，否则会误判迁移已结束
            pending_retry.append(v3_service_id)
            print(
                "save itsm v4 migration map error (unfinished, retry next init_system): {},"
                " approve_service_id is: {}".format(str(e), v3_service_id)
            )
        created_any = True

        _bind_process_applications(related_objs, workflow_key, v3_service_id, itsm_name, create_error)

    if not created_any:
        form_schema = {
            "type": "object",
            "required": ["ticket__title"],
            "properties": properties_base,
        }
        try:
            # 兜底流程不绑定具体 V3 服务，因此不写入迁移映射
            init_itsm_system(form_schema, default_workflow_name, default_workflow_desc, name_cache)
        except Exception as e:
            create_error[default_workflow_name] = default_workflow_name
            print(str(e))

    _write_system_id()

    # 存在未完成记录（V3 详情查询失败 / 流程创建失败等）=> 仍有套餐未能自动迁移，
    # 不标记整体完成，保留可恢复进度：下一轮 init_system 会跳过已迁移的、继续迁移剩余的。
    # 若确属永久失效（如服务已下架且无法恢复），可由运维排查对应 approve_service_id 后人工介入。
    if create_error or pending_retry:
        print(
            "[InitItsmV4] unfinished: pending_retry={}, create_error={}, will retry on next init_system".format(
                pending_retry, list(create_error.keys())
            )
        )
        return False
    return True


def _load_itsm_v4_migration_map() -> Dict[str, str]:
    """
    读取持久化的「V3 服务标识 -> V4 workflow_key」迁移映射。

    该映射是重试幂等的唯一依据：本地已记录的服务直接复用原流程，
    不重新解析名称，因此不受远端返回内容变化的影响。
    """

    migration_map = GlobalMetaConfig.get(ITSM_V4_MIGRATION_MAP_KEY, default={}) or {}
    return migration_map if isinstance(migration_map, dict) else {}


def _save_itsm_v4_migration_map(migration_map: Dict[str, str]) -> None:
    """
    持久化迁移映射：每解析出一个流程就落盘，保证进程中断后仍可恢复到同一个远端流程。
    """

    GlobalMetaConfig.set(
        config_key=ITSM_V4_MIGRATION_MAP_KEY,
        config_value=migration_map,
        config_level=ConfigLevelChoices.GLOBAL.value,
        instance_key=GLOBAL_CONFIG_LEVEL_INSTANCE,
    )


def _bind_process_applications(related_objs, workflow_key, v3_service_id, itsm_name, create_error) -> None:
    """
    把同一 V3 服务的所有处理套餐绑定到同一个 V4 workflow_key。
    """

    for obj in related_objs:
        try:
            obj.approve_service_id = workflow_key
            obj.save()
        except Exception as e:
            # 本地落库失败：下一轮该套餐仍带 V3 id，会通过迁移映射复用同一个
            # workflow_key 重新绑定，不会创建第二个流程
            create_error[str(v3_service_id)] = itsm_name
            print(str(e))


def _write_system_id():
    system_id = GlobalMetaConfig.get(ITSM_V4_SYSTEM_ID_KEY, default=None)
    # GlobalMetaConfig 配置的和环境变量配置的 system_id 一致，直接返回
    # system_id 的值由环境变量决定，以适用部署不同的环境
    if system_id == ITSM_V4_SYSTEM_CODE:
        print("[InitItsmV4] System ID already configured => %s, keep it" % system_id)
        return
    GlobalMetaConfig.set(
        config_key=ITSM_V4_SYSTEM_ID_KEY,
        config_value=ITSM_V4_SYSTEM_CODE,
        config_level=ConfigLevelChoices.GLOBAL.value,
        instance_key=GLOBAL_CONFIG_LEVEL_INSTANCE,
    )


def _fetch_existing_v4_keys():
    """
    分页拉全量已有流程，建立 name -> key 映射
    """
    existing_keys = {}
    try:
        page, page_size = 1, 200
        while True:
            resp = (
                api.bk_itsm_v4.system_workflow_list(system_id=ITSM_V4_SYSTEM_CODE, page=page, page_size=page_size) or {}
            )
            for item in resp.get("results") or []:
                if item.get("name") and item.get("key"):
                    existing_keys[item["name"]] = item["key"]
            if len(resp.get("results") or []) < page_size:
                break
            page += 1
    except APIRequestError:
        existing_keys = {}
    return existing_keys


def init_itsm_system(form_schema, itsm_v4_workflow_name, itsm_v4_workflow_desc, workflow_cache):
    """
    为指定的流程 name/desc/表单创建（或复用）一个 ITSM V4 系统流程，返回真实的 workflow_key。

    workflow_key 必须来自 SystemWorkflowCreate 的真实返回值，缺失直接抛 RuntimeError。
    system_workflow_create 的 name 在服务端有唯一约束，重复创建会报错，故按 name 去重：
    1. 先查本轮缓存（同一轮 init 内两个套餐算同名直接复用，避免二次创建撞约束）；
    2. 再分页拉全量已有流程（避免默认分页漏查导致误判不存在而重复创建）；
    3. 均不存在才真正创建，并写入缓存。
    """

    # 1. 本轮已创建/复用过的，直接返回
    if itsm_v4_workflow_name in workflow_cache:
        return workflow_cache[itsm_v4_workflow_name]
    existing_keys = _fetch_existing_v4_keys()

    if itsm_v4_workflow_name in existing_keys:
        workflow_key = existing_keys[itsm_v4_workflow_name]
        workflow_cache[itsm_v4_workflow_name] = workflow_key
        print("[InitItsmV4] System/Workflow Already Exists => %s" % workflow_key)
        return workflow_key

    # 3. 不存在则创建（系统已存在时 system_create 失败可忽略）
    try:
        api.bk_itsm_v4.system_create(
            **{
                "name": ITSM_V4_SYSTEM_NAME,
                "code": ITSM_V4_SYSTEM_CODE,
                "desc": ITSM_V4_SYSTEM_DESC,
            }
        )
    except Exception:
        pass
    try:
        result = api.bk_itsm_v4.system_workflow_create(
            **{
                "system_id": ITSM_V4_SYSTEM_CODE,
                "name": itsm_v4_workflow_name,
                "desc": itsm_v4_workflow_desc,
                "portal_id": ITSM_V4_WORKFLOW_PORTAL_ID,
                "app_id": ITSM_V4_WORKFLOW_APP_ID,
                "working_mode": ITSM_V4_WORKFLOW_WORKING_MODE,
                "operator": ITSM_V4_WORKFLOW_OPERATOR,
                "form_schema": form_schema,
            }
        )
    except Exception as e:
        raise Exception("[InitItsmV4]创建 Workflow 失败，终止后续步骤。返回内容：{}".format(str(e)))
    workflow_key = result["key"]
    workflow_cache[itsm_v4_workflow_name] = workflow_key
    print("[InitItsmV4] System/Workflow Created => %s" % workflow_key)
    return workflow_key


def create_iam_data_link(resource_type):
    if resource_type == "resource_type":
        config_key = RESOURCE_TYPE_DATA_CONFIG_KEY
        rt_key = RESOURCE_TYPE_DATA_RT_KEY
    elif resource_type == "action":
        config_key = ACTION_DATA_CONFIG_KEY
        rt_key = ACTION_DATA_RT_KEY
    elif resource_type == "user":
        config_key = USER_INFO_DATA_CONFIG_KEY
        rt_key = USER_INFO_DATA_RT_KEY
    else:
        raise Exception(f"ResourceType Does Not Support => {resource_type}")
    print(f"[CreateIAMDataLink] ConfigKey => {config_key}; RTKey => {rt_key}")
    config_name, bkbase_data_id = HttpPullHandler(resource_type).create_data_id()
    print(f"[CreateIAMDataLink] ConfigName => {config_name}; DataID => {bkbase_data_id}")
    clean_resp = PullCleanHandler(bkbase_data_id, config_name, resource_type).create_clean()
    storage_resp = PullStorageHandler(bkbase_data_id, config_name, resource_type).create_storage()
    GlobalMetaConfig.set(
        config_key,
        {
            "config_name": config_name,
            "bkbase_data_id": bkbase_data_id,
            "clean_resp": clean_resp,
            "storage_resp": storage_resp,
        },
    )
    GlobalMetaConfig.set(rt_key, f"{settings.DEFAULT_BK_BIZ_ID}_{config_name}")
