# -*- coding: utf-8 -*-
"""
WeSec API Mock 视图（仅用于 bkop 测试环境）

在 bkop 环境无法调用上云 WeSec API 时，用本地 JSON 文件模拟响应。
通过环境变量 BKSEC_MOCK_ENABLED=True 开启。
"""

import json
import os

from django.conf import settings
from django.http import JsonResponse
from django.views import View


class MockRiskAccessListView(View):
    """Mock GET /api/v1/risk/risk_access/ — 风险类型列表"""

    def get(self, request, *args, **kwargs):
        mock_file = os.path.join(settings.BASE_DIR, "mocks", "wesec", "risk_type_list.json")
        with open(mock_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JsonResponse(data, json_dumps_params={"ensure_ascii": False})
