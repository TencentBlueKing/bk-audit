# -*- coding: utf-8 -*-
from django.conf import settings

IAM_PERMISSION_BACKEND_V3 = "v3"
IAM_PERMISSION_BACKEND_V4 = "v4"


def get_iam_permission_backend() -> str:
    """Return the configured IAM backend, defaulting unknown values to V3 semantics."""
    backend = getattr(settings, "IAM_PERMISSION_BACKEND", IAM_PERMISSION_BACKEND_V3)
    if backend == IAM_PERMISSION_BACKEND_V4:
        return IAM_PERMISSION_BACKEND_V4
    return IAM_PERMISSION_BACKEND_V3


def is_iam_v4_backend() -> bool:
    """Whether the request path should use IAM V4 as the active permission backend."""
    return get_iam_permission_backend() == IAM_PERMISSION_BACKEND_V4


def is_iam_v3_backend() -> bool:
    """Whether the request path should use IAM V3 as the active permission backend."""
    return get_iam_permission_backend() == IAM_PERMISSION_BACKEND_V3
