"""同步查询的业务入口。

保留调用方SQL、COUNT和批量顺序，版本选择集中于此。
普通与调试查询仅区别上游地址；失败直接传播。
"""
from bk_resource import api

from services.web.bkbase.common import get_bkbase_version
from services.web.bkbase.constants import BKBaseVersion


def _resource(debug=False):
    service = api.bk_base_v4 if get_bkbase_version() == BKBaseVersion.V4 else api.bk_base
    return service.debug_query_sync if debug else service.query_sync


def query_sync(sql, *, prefer_storage=None, debug=False):
    """查询已构造SQL，不改变业务COUNT和分页语义。"""
    params = {"sql": sql}
    if prefer_storage is not None:
        params["prefer_storage"] = prefer_storage
    return _resource(debug)(**params)


def query_sync_bulk(requests, *, debug=False):
    """复用SDK有序批量查询及当前请求上下文。"""
    return _resource(debug).bulk_request(requests)
