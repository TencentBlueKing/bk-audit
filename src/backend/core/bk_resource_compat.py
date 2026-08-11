# -*- coding: utf-8 -*-
"""`bk-resource==0.4.11` 的临时兼容补丁。"""

from collections.abc import Mapping
from functools import wraps

from django.http import QueryDict
from django.utils.translation import gettext
from rest_framework.exceptions import ParseError


def apply_resource_viewset_request_data_compat():
    """避免 ResourceViewSet 合并路径参数时处理不可变或标量请求体。

    `bk-resource==0.4.11` 会在路由模板中直接对 ``request.data`` 调用
    ``update``。表单请求会得到不可变 ``QueryDict``，标量 JSON 则没有
    ``update`` 方法，都会泄漏为 500。上游修复并升级依赖后应删除本补丁。
    """
    from bk_resource.viewsets import ResourceViewSet

    if getattr(ResourceViewSet, "_bk_audit_request_data_compat_applied", False):
        return

    original_initial = ResourceViewSet.initial

    @wraps(original_initial)
    def initial(viewset, request, *args, **kwargs):
        original_initial(viewset, request, *args, **kwargs)

        # GET 请求在 bk-resource 模板内已通过 query_params.copy() 得到可变对象；
        # 仅当存在路径参数时，非 GET 请求才会在模板内执行 request_data.update(...)
        if request.method == "GET" or not viewset.kwargs:
            return

        request_data = request.data
        if isinstance(request_data, QueryDict):
            request._full_data = request_data.copy()
        elif not isinstance(request_data, Mapping):
            raise ParseError(gettext("请求体必须为 JSON/Form 对象，不能为字符串、数组或 null"))

    ResourceViewSet.initial = initial
    ResourceViewSet._bk_audit_request_data_compat_applied = True
