"""组合结果表详情、字段和敏感级别。

逻辑 ID 从正式 ResultTable 查询解析实际项目，再读取 Dataset 业务字段。
不共享缓存带个人收藏状态的完整Dataset。
"""
import re

from bk_resource import api

from services.web.bkbase import table_capabilities
from services.web.bkbase.common import get_bkbase_context
from services.web.bkbase.constants import (
    BKBaseVersion,
    TableBindingKind,
    VerifiedDatasetSensitivity,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError


def _context(context):
    return context if context is not None else get_bkbase_context()


def result_table_identity(context, result):
    """优先使用显式逻辑ID解析结果表身份，校验租户、标签和完整引用。"""
    if (
        not isinstance(result, dict)
        or result.get("kind", "ResultTable") != "ResultTable"
        or not isinstance(result.get("metadata"), dict)
        or not isinstance(result.get("spec"), dict)
    ):
        raise BKBaseResourceMappingError(message="Invalid ResultTable info")
    metadata, spec = result["metadata"], result["spec"]
    if any(not isinstance(metadata.get(key), str) or not metadata[key] for key in ("tenant", "namespace", "name")):
        raise BKBaseResourceMappingError(message="Incomplete ResultTable identity")
    if metadata["tenant"] != context.get("tenant"):
        raise BKBaseResourceMappingError(message="ResultTable tenant mismatch")
    labels = metadata.get("labels", {})
    if not isinstance(labels, dict):
        raise BKBaseResourceMappingError(message="Invalid ResultTable labels")
    logical_id = spec.get("predefiendResultTableId")
    biz_id = spec.get("bizId")
    if biz_id is not None and (isinstance(biz_id, bool) or not re.fullmatch(r"[0-9]+", str(biz_id))):
        raise BKBaseResourceMappingError(message="Invalid ResultTable business identity")
    if logical_id in (None, "") and biz_id is not None:
        logical_id = f"{biz_id}_{metadata['name'].replace('-', '_')}"
    label_id = labels.get("result_table_id")
    if logical_id in (None, ""):
        logical_id = label_id
    if not isinstance(logical_id, str) or not re.fullmatch(r"[0-9]+_[A-Za-z0-9_]+", logical_id):
        raise BKBaseResourceMappingError(message="Missing or invalid ResultTable logical identity")
    if label_id not in (None, "", logical_id):
        raise BKBaseResourceMappingError(message="Conflicting ResultTable logical identities")
    return {"kind": "ResultTable", **{key: metadata[key] for key in ("tenant", "namespace", "name")}}, logical_id


def get_result_table_ref(context, result_table_id):
    """按逻辑 ID 解析同租户任意项目的权威引用，不依赖存储绑定。"""
    if (
        not isinstance(result_table_id, str)
        or not re.fullmatch(r"[0-9]+_[A-Za-z0-9_]+", result_table_id)
        or not isinstance(context.get("tenant"), str)
        or not context["tenant"]
    ):
        raise BKBaseResourceMappingError(message="Invalid ResultTable logical ID or tenant")
    result = api.bk_base_v4.result_table_info(tenant=context["tenant"], result_table_id=result_table_id)
    ref, logical_id = result_table_identity(context, result)
    if logical_id != result_table_id:
        raise BKBaseResourceMappingError(message="ResultTable logical identity mismatch")
    return ref


def get_source_capabilities(result_table_id, *, context=None):
    """从正式结果表和就绪 Binding 读取输入能力，避免借用 V3 表分类。"""
    context = _context(context)
    if not isinstance(result_table_id, str) or not re.fullmatch(r"[0-9]+_[A-Za-z0-9_]+", result_table_id):
        raise BKBaseResourceMappingError(message="Invalid ResultTable logical ID")
    if not isinstance(context.get("tenant"), str) or not context["tenant"]:
        raise BKBaseResourceMappingError(message="Missing ResultTable tenant")
    result = api.bk_base_v4.result_table_info(tenant=context["tenant"], result_table_id=result_table_id)
    ref, logical_id = result_table_identity(context, result)
    if logical_id != result_table_id:
        raise BKBaseResourceMappingError(message="ResultTable logical identity mismatch")
    capabilities = table_capabilities.parse_bindings(result, ref)
    if not capabilities["channel"]:
        # Dataset 允许存储视角匹配不到时回退，须同时确认逻辑表、kind 和 storage_type。
        channel = api.bk_base_v4.dataset_detail(
            tenant=context["tenant"],
            namespace=ref["namespace"],
            dataset_name=result_table_id,
            storage_type="channel",
        )
        if not isinstance(channel, dict) or channel.get("dataset_name") != result_table_id:
            raise BKBaseResourceMappingError(message="Channel Dataset logical identity mismatch")
        capabilities["channel"] = (
            channel.get("kind") == TableBindingKind.CHANNEL and channel.get("storage_type") == "channel"
        )
    return capabilities


def _dataset_namespace(context, result_table_id):
    """优先沿用可信项目映射，缺失时读取正式逻辑结果表身份。"""
    namespace = context.get("rt_namespaces", {}).get(result_table_id)
    if namespace is None:
        namespace = get_result_table_ref(context, result_table_id)["namespace"]
    if not context.get("tenant") or not isinstance(namespace, str) or not namespace:
        raise BKBaseResourceMappingError(message="Missing trusted dataset namespace")
    return namespace


def get_result_table(result_table_id, related=None, *, context=None):
    """读取单表元数据，保留现有业务字段。"""
    context = _context(context)
    params = {"result_table_id": result_table_id}
    if related is not None:
        params["related"] = list(related)
    if context["version"] == BKBaseVersion.V3:
        return api.bk_base.get_result_table(**params)
    namespace = _dataset_namespace(context, result_table_id)
    prefix, separator, suffix = result_table_id.partition("_")
    if not separator or not prefix.isascii() or not prefix.isdecimal() or not suffix:
        raise BKBaseResourceMappingError(message="Invalid dataset name")
    result = api.bk_base_v4.dataset_detail(tenant=context["tenant"], namespace=namespace, dataset_name=result_table_id)
    if not isinstance(result, dict) or result.get("dataset_name") != result_table_id:
        raise BKBaseResourceMappingError(message=f"Invalid metadata for {result_table_id}")
    projected = {
        "result_table_id": result_table_id,
        "result_table_name": result.get("dataset_alias", ""),
        "result_table_name_alias": result.get("dataset_alias", ""),
        "bk_biz_id": int(prefix),
        "data_set_type": result.get("data_set_type"),
    }
    if "fields" in result:
        if not isinstance(result["fields"], list):
            raise BKBaseResourceMappingError(message=f"Invalid fields for {result_table_id}")
        projected["fields"] = result["fields"]
    if related is None or "storages" in related:
        rows = list_datasets({**context, "namespace": namespace}, dataset_name=result_table_id)
        storages = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("dataset_name"), str):
                raise BKBaseResourceMappingError(message="Invalid dataset list row")
            if row["dataset_name"] != result_table_id:
                continue
            kind = row.get("storage_type")
            if not isinstance(kind, str):
                raise BKBaseResourceMappingError(message="Invalid dataset storage type")
            if kind:
                storages[kind] = {"storage_type": kind}
        projected["storages"] = storages
    return projected


def get_result_tables(result_table_ids, related=None, *, context=None):
    """按输入ID关联结果，不依赖并发完成先后。"""
    context = _context(context)
    if context["version"] == BKBaseVersion.V3:
        params = {"result_table_ids": result_table_ids}
        if related is not None:
            params["related"] = related
        return api.bk_base.get_result_tables(**params)
    return [get_result_table(rt_id, related, context=context) for rt_id in result_table_ids]


def get_result_tables_bulk(requests):
    """保留旧批量分组的结果结构。"""
    context = get_bkbase_context()
    if context["version"] == BKBaseVersion.V3:
        return api.bk_base.get_result_tables.bulk_request(requests)
    return [get_result_tables(context=context, **params) for params in requests]


def get_rt_fields(result_table_id, *, context=None):
    """逻辑字段与实际存储schema不混用。"""
    context = _context(context)
    if context["version"] == BKBaseVersion.V3:
        return api.bk_base.get_rt_fields(result_table_id=result_table_id)
    result = get_result_table(result_table_id, related=["fields"], context=context)
    if not isinstance(result.get("fields"), list):
        raise BKBaseResourceMappingError(message=f"Missing fields for {result_table_id}")
    return result["fields"]


def get_rt_sensitivity(context, rt_id):
    """只返回敏感度，禁止把当前策略namespace猜作输入表归属。"""
    namespace = _dataset_namespace(context, rt_id)
    result = api.bk_base_v4.dataset_detail(tenant=context["tenant"], namespace=namespace, dataset_name=rt_id)
    sensitivity = result.get("sensitivity")
    if sensitivity in VerifiedDatasetSensitivity.values:
        # Dataset不提供业务角色成员，不能由敏感级别推断授权或补造成员。
        return {"level": sensitivity}
    raise BKBaseResourceMappingError(message=f"Missing or unsupported sensitivity for {rt_id}")


def get_sensitivity_info_via_dataset(**params):
    """维持业务敏感度入口，V4按可信引用查询Dataset。"""
    context = get_bkbase_context()
    if context["version"] == BKBaseVersion.V3:
        return api.bk_base.get_sensitivity_info_via_dataset(**params)
    return get_rt_sensitivity(context, params["data_set_id"])


def list_datasets(context, *, dataset_name=None, user_request=None):
    """按 total 记录数分页；显式传入 request 时使用个人接口身份。"""
    if not context.get("tenant") or not context.get("namespace"):
        raise BKBaseResourceMappingError(message="Missing dataset namespace")
    rows, page = [], 1
    while True:
        params = {"tenant": context["tenant"], "namespace": context["namespace"], "page": page, "page_size": 100}
        if dataset_name is not None:
            params["dataset_name"] = dataset_name
        if user_request is not None:
            params["_request"] = user_request
            result = api.bk_base_v4.user_dataset_list(**params)
        else:
            result = api.bk_base_v4.dataset_list(**params)
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("list"), list)
            or type(result.get("total")) is not int
            or result["total"] < 0
        ):
            raise BKBaseResourceMappingError(message="Invalid dataset pagination response")
        rows.extend(result["list"])
        if not result["list"] or page * params["page_size"] >= result["total"]:
            return rows
        page += 1


def metadata_cache_scope():
    """完整MCP元数据含全部存储视角，Dataset个人状态不放共享缓存。"""
    context = get_bkbase_context()
    return f"v4:{context['tenant']}" if context["version"] == BKBaseVersion.V4 else ""
