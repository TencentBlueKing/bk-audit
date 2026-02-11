# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import datetime

from django import forms
from django.contrib import admin
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.sql.constants import FieldType, Operator
from services.web.risk.handlers.subscription_sql import RiskEventSubscriptionSQLBuilder
from services.web.risk.models import (
    ManualEvent,
    ProcessApplication,
    Risk,
    RiskEventSubscription,
    RiskExperience,
    RiskReport,
    RiskRule,
    TicketNode,
    TicketPermission,
)
from services.web.risk.widgets import WhereConditionWidget


class StrategyFilter(admin.SimpleListFilter):
    title = _("命中策略")
    parameter_name = "strategy"
    # 缓存键和超时时间
    CACHE_KEY = "risk_admin:strategy_filter:lookups"
    CACHE_TIMEOUT = 300  # 5 分钟缓存

    def lookups(self, request, model_admin):
        # 使用缓存避免每次加载页面都执行全表 distinct() 查询
        cached_lookups = cache.get(self.CACHE_KEY)
        if cached_lookups is not None:
            return cached_lookups

        # 仅展示当前风险单中实际命中的策略，避免全量策略过多
        strategy_ids = list(Risk.objects.values_list("strategy_id", flat=True).distinct().order_by())
        from services.web.strategy_v2.models import Strategy

        strategies = Strategy.objects.filter(strategy_id__in=strategy_ids).only("strategy_id", "strategy_name")
        lookups = [(str(s.strategy_id), s.strategy_name or str(s.strategy_id)) for s in strategies]

        # 缓存结果
        cache.set(self.CACHE_KEY, lookups, self.CACHE_TIMEOUT)
        return lookups

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(strategy_id=value)
        return queryset


@admin.register(Risk)
class RiskAdmin(admin.ModelAdmin):
    # 截断展示的最大长度
    TRUNCATE_MAX_LENGTH = 100
    # JSONField 展示的最大元素数量
    JSON_MAX_ITEMS = 3

    list_display = [
        "risk_id",
        "title_short",
        "strategy",
        "operator_short",
        "event_time",
        "status",
        "display_status",
        "current_operator_short",
        "notice_users_short",
        "risk_label",
        "manual_synced",
        "auto_generate_report",
    ]
    # 支持按策略名搜索
    search_fields = ["risk_id", "title", "strategy__strategy_name"]
    # 支持基于命中策略过滤
    list_filter = ["status", "display_status", "risk_label", "manual_synced", "auto_generate_report", StrategyFilter]
    list_per_page = 50  # 减少每页数量以提升性能

    def get_queryset(self, request):
        """
        Admin 专用的轻量级 queryset：
        1. defer 所有不在 list_display 中直接使用的大字段
        2. 使用 select_related 避免 N+1 查询
        """
        return Risk.objects.defer("event_content", "event_evidence", "event_data").select_related("strategy")

    def _truncate_text_field(self, value: str, max_length: int = None) -> str:
        """截断 TextField 展示"""
        if not value:
            return ""
        max_len = max_length or self.TRUNCATE_MAX_LENGTH
        return value[:max_len] + "..." if len(value) > max_len else value

    def _truncate_json_field(self, value, max_items: int = None, max_length: int = None) -> str:
        """截断 JSONField 展示"""
        if not value:
            return ""
        max_items = max_items or self.JSON_MAX_ITEMS
        max_len = max_length or self.TRUNCATE_MAX_LENGTH
        if isinstance(value, list):
            display = ", ".join(str(v) for v in value[:max_items])
            if len(value) > max_items:
                display += f" (+{len(value) - max_items})"
        else:
            display = str(value)
        return display[:max_len] + "..." if len(display) > max_len else display

    def title_short(self, obj: Risk) -> str:
        return self._truncate_text_field(obj.title)

    title_short.short_description = _("风险标题")

    def operator_short(self, obj: Risk) -> str:
        return self._truncate_json_field(obj.operator)

    operator_short.short_description = _("责任人")

    def current_operator_short(self, obj: Risk) -> str:
        return self._truncate_json_field(obj.current_operator)

    current_operator_short.short_description = _("当前处理人")

    def notice_users_short(self, obj: Risk) -> str:
        return self._truncate_json_field(obj.notice_users)

    notice_users_short.short_description = _("关注人")


@admin.register(ProcessApplication)
class ProcessApplicationAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "need_approve", "is_deleted"]
    search_fields = ["id", "name"]
    list_filter = ["is_deleted"]


@admin.register(RiskRule)
class RiskRuleAdmin(admin.ModelAdmin):
    list_display = ["id", "rule_id", "version", "name", "auto_close_risk", "priority_index", "is_enabled", "is_deleted"]
    search_fields = ["rule_id", "name"]
    list_filter = ["auto_close_risk", "is_enabled", "is_deleted"]


@admin.register(RiskExperience)
class RiskExperienceAdmin(admin.ModelAdmin):
    list_display = ["risk_id", "content", "created_by", "created_at", "is_deleted"]
    search_fields = ["risk_id", "created_by"]
    list_filter = ["is_deleted"]


@admin.register(ManualEvent)
class ManualEventAdmin(admin.ModelAdmin):
    list_display = [
        "manual_event_id",
        "title",
        "strategy",
        "raw_event_id",
        "event_time",
        "status",
        "risk_label",
        "manual_synced",
    ]
    search_fields = ["manual_event_id", "raw_event_id", "title"]
    list_filter = ["status", "risk_label", "strategy", "manual_synced"]
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]


@admin.register(TicketNode)
class TicketNodeAdmin(admin.ModelAdmin):
    list_display = ["id", "risk_id", "action", "operator", "current_operator", "time", "status"]
    list_filter = ["action", "status"]
    search_fields = ["risk_id"]


@admin.register(TicketPermission)
class TicketPermissionAdmin(admin.ModelAdmin):
    list_display = ["id", "risk_id", "action", "user"]
    search_fields = ["risk_id", "user"]
    list_filter = ["action"]


class RiskEventSubscriptionAdminForm(forms.ModelForm):
    condition = forms.JSONField(required=False, help_text=_("可使用结构化模式或 JSON 模式编辑筛选条件。"))

    class Meta:
        model = RiskEventSubscription
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["condition"].widget = WhereConditionWidget(
            field_options=self._build_condition_field_options(),
            operator_options=list(Operator.choices),
            field_type_options=list(FieldType.choices),
        )

    @staticmethod
    def _build_condition_field_options():
        return RiskEventSubscriptionSQLBuilder.get_field_metadata()

    def clean_condition(self):
        condition = self.cleaned_data.get("condition") or {}
        try:
            RiskEventSubscription.validate_condition_dict(condition)
        except DjangoValidationError as exc:  # pragma: no cover - admin 校验
            raise forms.ValidationError(exc) from exc
        return condition


@admin.register(RiskEventSubscription)
class RiskEventSubscriptionAdmin(admin.ModelAdmin):
    change_form_template = "admin/risk/risk_event_subscription/change_form.html"
    form = RiskEventSubscriptionAdminForm
    list_display = ["token", "name", "namespace", "is_enabled", "updated_at", "is_deleted"]
    list_filter = ["namespace", "is_enabled", "is_deleted"]
    search_fields = ["token", "name", "description"]
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]
    fieldsets = (
        (None, {"fields": ("token", "name", "namespace", "is_enabled")}),
        (_("Metadata"), {"fields": ("description", "condition")}),
        (_("Audit"), {"fields": ("created_by", "created_at", "updated_by", "updated_at"), "classes": ("collapse",)}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/preview-sql/",
                self.admin_site.admin_view(self.preview_sql_view),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_preview_sql",
            ),
        ]
        return custom + urls

    def preview_sql_view(self, request, object_id, *args, **kwargs):
        subscription = self.get_object(request, object_id)
        if not subscription:
            change_url = reverse(f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist")
            return TemplateResponse(
                request,
                "admin/risk/risk_event_subscription/preview_sql.html",
                {
                    **self.admin_site.each_context(request),
                    "opts": self.model._meta,
                    "title": _("订阅不存在"),
                    "api_url": "/api/v1/risk_event_subscription_admin/preview/",
                    "original": None,
                    "initial": self._default_preview_initial(),
                    "back_url": change_url,
                },
            )

        change_url = reverse(
            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
            args=[subscription.pk],
        )
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": subscription,
            "title": _("验证 SQL - {name}").format(name=str(subscription)),
            "api_url": "/api/v1/risk_event_subscription_admin/preview/",
            "initial": self._default_preview_initial(),
            "back_url": request.GET.get("next") or change_url,
        }
        return TemplateResponse(request, "admin/risk/risk_event_subscription/preview_sql.html", context)

    def _default_preview_initial(self):
        now = timezone.localtime()
        return {
            "start_time": now - datetime.timedelta(hours=1),
            "end_time": now,
            "page": 1,
            "page_size": 10,
        }


@admin.register(RiskReport)
class RiskReportAdmin(admin.ModelAdmin):
    list_display = [
        "risk",
        "status",
        "content_short",
        "created_at",
        "updated_at",
    ]
    search_fields = ["risk__risk_id"]
    list_filter = ["status"]
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]
    raw_id_fields = ["risk"]

    def content_short(self, obj: RiskReport):
        """显示报告内容的前100个字符"""
        if obj.content:
            return obj.content[:100] + "..." if len(obj.content) > 100 else obj.content
        return ""

    content_short.short_description = _("报告内容摘要")
