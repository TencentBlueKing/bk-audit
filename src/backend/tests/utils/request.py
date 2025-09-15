# -*- coding: utf-8 -*-

from types import SimpleNamespace
from typing import Any, Callable, Dict

from blueapps.utils.local import request_local
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory


def call_resource_with_request(func: Callable[..., Any], data: Dict[str, Any]):
    """
    Wrap resource call with a DRF Request so resources with bind_request=True
    receive `_request` as expected.
    """
    factory = APIRequestFactory()
    django_request = factory.post('/fake-url/', data, format='json')

    # default mock user for audit context (both Django and DRF request)
    mock_user = SimpleNamespace(username='admin', is_authenticated=True)
    drf_request = Request(django_request)
    drf_request.user = mock_user
    setattr(request_local, "request", drf_request)
    # call resource with kwargs
    resp = func(_request=drf_request, **data)
    # normalize: return DRF Response.data when available
    return resp.data
