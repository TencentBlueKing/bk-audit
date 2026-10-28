"""组合结果表详情、字段和敏感级别。

已知RT以MCP元数据为准，Dataset访问要求明确项目归属。
不共享缓存带个人收藏状态的完整Dataset。
"""
from bk_resource import api

from services.web.bkbase.common import get_bkbase_context
from services.web.bkbase.constants import BKBaseVersion, VerifiedDatasetSensitivity
from services.web.bkbase.exceptions import BKBaseResourceMappingError


def _context(context):
    return context if context is not None else get_bkbase_context()


def get_result_table(result_table_id, related=None, *, context=None):
    """读取单表元数据，保留现有业务字段。"""
    context = _context(context)
    params = {"result_table_id": result_table_id}
    if related is not None:
        params["related"] = list(related)
    if context["version"] == BKBaseVersion.V3:
        return api.bk_base.get_result_table(**params)
    result = api.bk_base_v4.result_table(**params)
    if not isinstance(result, dict) or result.get("result_table_id") != result_table_id:
        raise BKBaseResourceMappingError(message=f"Invalid metadata for {result_table_id}")
    return result


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
    namespace = context.get("rt_namespaces", {}).get(rt_id)
    if not namespace:
        raise BKBaseResourceMappingError(message=f"Missing namespace mapping for {rt_id}")
    result = api.bk_base_v4.dataset_detail(namespace=namespace, dataset_name=rt_id)
    sensitivity = result.get("sensitivity")
    if isinstance(sensitivity, dict):
        return sensitivity
    if sensitivity == VerifiedDatasetSensitivity.PRIVATE:
        # Dataset不提供业务角色成员，不能由敏感级别推断授权或补造成员。
        return {"level": sensitivity}
    raise BKBaseResourceMappingError(message=f"Missing or unsupported sensitivity for {rt_id}")


def get_sensitivity_info_via_dataset(**params):
    """维持业务敏感度入口，V4按可信引用查询Dataset。"""
    context = get_bkbase_context()
    if context["version"] == BKBaseVersion.V3:
        return api.bk_base.get_sensitivity_info_via_dataset(**params)
    return get_rt_sensitivity(context, params["data_set_id"])


def list_datasets(context):
    """pages_num为总页数；total不能用作页数循环。"""
    if not context.get("namespace"):
        raise BKBaseResourceMappingError(message="Missing dataset namespace")
    rows, page = [], 1
    while True:
        result = api.bk_base_v4.dataset_list(namespace=context["namespace"], page=page, page_size=100)
        if not isinstance(result.get("list"), list) or not isinstance(result.get("pages_num"), int):
            raise BKBaseResourceMappingError(message="Invalid dataset pagination response")
        rows.extend(result["list"])
        if page >= result["pages_num"]:
            return rows
        page += 1


def metadata_cache_scope():
    """完整MCP元数据含全部存储视角，Dataset个人状态不放共享缓存。"""
    context = get_bkbase_context()
    return f"v4:{context['tenant']}" if context["version"] == BKBaseVersion.V4 else ""
