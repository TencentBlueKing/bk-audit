"""组合结果表详情、字段和敏感级别。

逻辑 ID 从正式 ResultTable 查询解析实际项目，再读取 Dataset 业务字段。
不共享缓存带个人收藏状态的完整Dataset。
"""
import re
from concurrent.futures import FIRST_COMPLETED, CancelledError, ThreadPoolExecutor, wait
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from threading import Event
from time import monotonic

from bk_resource import api
from requests.exceptions import ConnectionError as RequestConnectionError
from requests.exceptions import Timeout as RequestTimeout
from urllib3.exceptions import ReadTimeoutError

from api.bk_base_v4.default import READ_DEADLINE
from services.web.bkbase import table_capabilities
from services.web.bkbase.common import get_bkbase_context
from services.web.bkbase.constants import (
    BKBaseVersion,
    TableBindingKind,
    VerifiedDatasetSensitivity,
)
from services.web.bkbase.exceptions import BKBaseReadTimeout, BKBaseResourceMappingError

LIST_READ_BUDGET_SECONDS = 50.0
LIST_READ_WORKERS = 16
_READ_CANCELLED = ContextVar("bkbase_list_read_cancelled", default=None)


def _remaining_read_time():
    """翻页、派发和返回前检查本次读取的取消信号及预算。"""
    cancelled = _READ_CANCELLED.get()
    if cancelled is not None and cancelled.is_set():
        raise CancelledError("BKBase list read cancelled")
    deadline = READ_DEADLINE.get()
    if deadline is None:
        return None
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise BKBaseReadTimeout()
    return remaining


def _is_request_timeout(error):
    """沿显式cause识别超时，兼容requests将响应体读超时包装为ConnectionError。"""
    visited = set()
    while error is not None and id(error) not in visited:
        visited.add(id(error))
        if isinstance(error, RequestTimeout) or (
            isinstance(error, RequestConnectionError) and error.args and isinstance(error.args[0], ReadTimeoutError)
        ):
            return True
        error = error.__cause__
    return False


@contextmanager
def list_read_scope():
    """嵌套调用和工作线程共享本次预算及取消信号，退出后恢复上下文。"""
    token, cancel_token = None, None
    if READ_DEADLINE.get() is None:
        token = READ_DEADLINE.set(monotonic() + LIST_READ_BUDGET_SECONDS)
    if _READ_CANCELLED.get() is None:
        cancel_token = _READ_CANCELLED.set(Event())
    try:
        _remaining_read_time()
        yield
        _remaining_read_time()
    except Exception as error:
        if not isinstance(error, BKBaseReadTimeout) and (
            _is_request_timeout(error) or (not _READ_CANCELLED.get().is_set() and monotonic() >= READ_DEADLINE.get())
        ):
            raise BKBaseReadTimeout() from error
        raise
    finally:
        if cancel_token is not None:
            _READ_CANCELLED.reset(cancel_token)
        if token is not None:
            READ_DEADLINE.reset(token)


def bounded_read_map(function, items):
    """最多保留一窗任务并按输入顺序返回；首错停止后续分页，等待在途读取。"""
    items = list(items)
    if not items:
        return []
    with list_read_scope():
        results = [None] * len(items)
        executor = ThreadPoolExecutor(max_workers=min(LIST_READ_WORKERS, len(items)), thread_name_prefix="bkbase-list")
        pending, index = {}, 0
        try:
            while index < len(items) or pending:
                _remaining_read_time()
                while index < len(items) and len(pending) < LIST_READ_WORKERS:
                    _remaining_read_time()
                    pending[executor.submit(copy_context().run, function, items[index])] = index
                    index += 1
                done, _ = wait(pending, timeout=_remaining_read_time(), return_when=FIRST_COMPLETED)
                if not done:
                    raise BKBaseReadTimeout()
                for future in done:
                    results[pending[future]] = future.result()
                for future in done:
                    del pending[future]
            return results
        except BaseException:
            # 先阻止已运行任务继续翻页，再等待在途GET；主线程保留首个错误。
            _READ_CANCELLED.get().set()
            raise
        finally:
            for future in pending:
                future.cancel()
            executor.shutdown(wait=True, cancel_futures=True)


def _context(context):
    return context if context is not None else get_bkbase_context()


def _result_table_info(context, result_table_id):
    """只在本次候选展开中复用原始RT；权限列表及不同请求之间不共享。"""
    cache = context.get("_result_table_info")
    key = (context["tenant"], result_table_id)
    if cache is not None and key in cache:
        return cache[key]
    result = api.bk_base_v4.result_table_info(tenant=context["tenant"], result_table_id=result_table_id)
    if cache is not None:
        cache[key] = result
    return result


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
    result = _result_table_info(context, result_table_id)
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
    result = _result_table_info(context, result_table_id)
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


def get_result_tables_with_capabilities(result_table_ids, *, context=None):
    """候选只读取需要的正式详情/能力，共用RT身份且不展开未消费的存储列表。"""
    context = {**_context(context), "_result_table_info": {}}
    identifiers = list(dict.fromkeys(result_table_ids))
    return bounded_read_map(
        lambda rt_id: (
            get_result_table(rt_id, related=[], context=context),
            get_source_capabilities(rt_id, context=context),
        ),
        identifiers,
    )


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
        _remaining_read_time()
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
        if user_request is not None and not result["list"] and len(rows) < result["total"]:
            raise BKBaseResourceMappingError(message="User Dataset pagination ended before total")
        if not result["list"] or page * params["page_size"] >= result["total"]:
            return rows
        page += 1


def metadata_cache_scope():
    """完整MCP元数据含全部存储视角，Dataset个人状态不放共享缓存。"""
    context = get_bkbase_context()
    return f"v4:{context['tenant']}" if context["version"] == BKBaseVersion.V4 else ""
