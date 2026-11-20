"""统一同步查询入口。

Query协议不随BKBASE_API_VERSION切换，复用已有V3 Resource及可配置action。
保留SQL、COUNT、批量顺序和调试地址；BKBase内部转发V4，失败直接传播。
"""
from bk_resource import api


def _resource(debug=False, safe=False):
    service = api.bk_base
    if safe and not debug:
        return service.safe_query_sync
    return service.debug_query_sync if debug else service.query_sync


def query_sync(sql, *, prefer_storage=None, debug=False, safe=False):
    """查询已构造SQL，不改变业务COUNT和分页语义。"""
    params = {"sql": sql}
    if prefer_storage is not None:
        params["prefer_storage"] = prefer_storage
    return _resource(debug, safe)(**params)


def query_sync_bulk(requests, *, debug=False, safe=False):
    """复用 SDK 有序批量查询；日志工具保留 V3 SafeQuerySync 诊断行为。"""
    return _resource(debug, safe).bulk_request(requests)
