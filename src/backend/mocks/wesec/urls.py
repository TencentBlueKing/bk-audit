# -*- coding: utf-8 -*-
"""
WeSec API Mock URL 配置（仅用于 bkop 测试环境）
"""

from django.urls import path

from mocks.wesec.views import MockRiskAccessListView

urlpatterns = [
    path("api/v1/risk/risk_access/", MockRiskAccessListView.as_view(), name="mock-risk-access-list"),
]
