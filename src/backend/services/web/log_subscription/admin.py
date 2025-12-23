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
import json
import uuid

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.sql.constants import FieldType, Operator
from core.sql.model import WhereCondition
from services.web.log_subscription.models import (
    LogDataSource,
    LogSubscription,
    LogSubscriptionItem,
)
from services.web.risk.widgets import WhereConditionWidget


class SafeJSONField(forms.JSONField):
    """
    安全的 JSONField，处理已经是字典的情况

    Django 的 JSONField 在 bound_data 中期望接收字符串，但有时数据已经是字典格式。
    这个字段会处理两种情况：字符串和字典。
    """

    def bound_data(self, data, initial):
        """
        处理绑定数据，支持字符串和已解析的 JSON 对象（dict/list）

        Django 的 JSONField.bound_data 期望接收字符串，但有时数据已经是解析后的对象。
        这个方法会处理两种情况。
        """
        if data is None:
            return initial

        # 如果已经是 JSON 对象（字典或列表），直接返回
        # 这通常发生在从数据库加载数据时，JSONField 已经自动反序列化
        if isinstance(data, (dict, list)):
            return data

        # 如果是字符串，尝试解析
        if isinstance(data, (str, bytes, bytearray)):
            try:
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                return json.loads(data)
            except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                return data

        # 其他情况直接返回
        return data


@admin.register(LogDataSource)
class LogDataSourceAdmin(admin.ModelAdmin):
    """日志数据源管理"""

    list_display = ["source_id", "name", "namespace", "storage_type", "is_enabled", "updated_at"]
    list_filter = ["namespace", "storage_type", "is_enabled"]
    search_fields = ["source_id", "name", "description"]
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]

    fieldsets = (
        (None, {"fields": ("source_id", "name", "namespace", "is_enabled")}),
        (
            _("表配置"),
            {
                "fields": ("bkbase_table_id", "storage_type", "time_field"),
                "description": _(
                    "bkbase_table_id: BKBase 结果表 ID，如 591_bkaudit_event<br>"
                    "storage_type: 存储类型，默认 doris<br>"
                    "time_field: 用于时间范围筛选的字段名"
                ),
            },
        ),
        (
            _("必须筛选字段"),
            {
                "fields": ("required_filter_fields",),
                "description": _(
                    "订阅配置项选择此数据源时，筛选条件中必须包含的字段列表<br>"
                    '格式: ["field1", "field2"]<br>'
                    "注意: 这里只校验字段名是否在筛选条件中，字段是否真实存在交由 SQL 查询时数据库校验"
                ),
            },
        ),
        (_("其他"), {"fields": ("description",)}),
        (
            _("审计信息"),
            {"fields": ("created_by", "created_at", "updated_by", "updated_at"), "classes": ("collapse",)},
        ),
    )


# ============================================
# 订阅配置项表单（必须在 Inline 之前定义）
# ============================================


class LogSubscriptionItemAdminForm(forms.ModelForm):
    """订阅配置项表单"""

    condition = SafeJSONField(required=False, help_text=_("可使用结构化模式或 JSON 模式编辑筛选条件。"))

    class Meta:
        model = LogSubscriptionItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 确保 condition 字段不是必填的
        self.fields["condition"].required = False

        # 过滤数据源，只显示启用的数据源
        if "data_sources" in self.fields:
            self.fields["data_sources"].queryset = LogDataSource.objects.filter(is_enabled=True)

        # 由于不再管理字段元数据，这里提供基础的 Widget 配置
        # 字段选项为空，用户需要手动输入字段名
        self.fields["condition"].widget = WhereConditionWidget(
            field_options=[],  # 不提供预定义字段，用户自行输入
            operator_options=list(Operator.choices),
            field_type_options=list(FieldType.choices),
        )

    def clean_condition(self):
        """验证筛选条件"""
        condition = self.cleaned_data.get("condition")

        # 如果为空，返回空字典（允许不配置筛选条件）
        if not condition:
            return {}

        # 验证 WhereCondition 格式
        try:
            WhereCondition.model_validate(condition)
        except Exception as exc:
            raise forms.ValidationError(str(exc))

        return condition

    def clean(self):
        """
        表单整体验证
        """
        cleaned_data = super().clean()

        # 基本验证：如果选择了数据源，检查是否需要配置筛选条件
        data_sources = None

        if self.instance and self.instance.pk:
            # 编辑现有配置项
            data_sources = self.instance.data_sources.all()
        elif "data_sources" in cleaned_data:
            # 内联添加新配置项
            data_sources = cleaned_data.get("data_sources")

        condition_data = cleaned_data.get("condition")

        if data_sources:
            # 1. 检查是否有数据源要求必须筛选字段，但条件为空
            sources_with_required = [source for source in data_sources if source.required_filter_fields]
            if sources_with_required and not condition_data:
                source_names = ", ".join([s.name for s in sources_with_required])
                raise forms.ValidationError({"condition": _("以下数据源要求配置筛选条件：{sources}").format(sources=source_names)})

            # 2. 深度校验：检查条件中是否包含了必须的字段
            # 将字典转换为 WhereCondition 对象以便调用模型的校验逻辑
            if condition_data:
                try:
                    where_condition = WhereCondition.model_validate(condition_data)
                    # 收集所有数据源的错误，而不是遇到第一个错误就抛出
                    validation_errors = []
                    for source in data_sources:
                        try:
                            source.validate_required_fields(where_condition)
                        except DjangoValidationError as e:
                            # 收集每个数据源的错误信息
                            if hasattr(e, "message_dict") and "condition" in e.message_dict:
                                validation_errors.extend(e.message_dict["condition"])
                            elif hasattr(e, "messages"):
                                validation_errors.extend(e.messages if isinstance(e.messages, list) else [e.messages])
                            else:
                                validation_errors.append(str(e))

                    # 如果有任何验证错误，统一抛出
                    if validation_errors:
                        raise forms.ValidationError({"condition": validation_errors})
                except forms.ValidationError:
                    # 重新抛出表单验证错误
                    raise
                except DjangoValidationError as e:
                    # 将模型层的错误转化为表单错误，这样页面上能红字显示
                    if hasattr(e, "message_dict"):
                        raise forms.ValidationError(e.message_dict)
                    elif hasattr(e, "messages"):
                        error_list = e.messages if isinstance(e.messages, list) else [e.messages]
                        raise forms.ValidationError({"condition": error_list})
                    else:
                        raise forms.ValidationError({"condition": [str(e)]})
                except Exception as e:
                    # 兜底捕获其他可能的解析错误
                    raise forms.ValidationError({"condition": [str(e)]})

        return cleaned_data


# ============================================
# 订阅配置项内联编辑
# ============================================


class LogSubscriptionItemInline(admin.StackedInline):
    """订阅配置项内联编辑"""

    model = LogSubscriptionItem
    extra = 0  # 不自动显示空行，通过"添加另一个"按钮添加
    can_delete = True
    show_change_link = True  # 显示编辑链接，可跳转到独立页面进行更复杂的编辑

    # 使用自定义表单以支持 WhereConditionWidget
    form = LogSubscriptionItemAdminForm

    fieldsets = (
        (None, {"fields": ("name", "order")}),
        (_("数据源"), {"fields": ("data_sources",)}),
        (_("筛选条件"), {"fields": ("condition",)}),
        (_("描述"), {"fields": ("description",)}),
    )

    # 设置 filter_horizontal 以便更好地选择多个数据源
    filter_horizontal = ["data_sources"]


@admin.register(LogSubscription)
class LogSubscriptionAdmin(admin.ModelAdmin):
    """日志订阅配置管理"""

    change_form_template = "admin/log_subscription/change_form.html"
    list_display = ["name", "token", "is_enabled", "get_items_count", "updated_at", "is_deleted"]
    list_filter = ["is_enabled", "is_deleted"]
    search_fields = ["name", "token", "description"]
    readonly_fields = ["token", "created_by", "created_at", "updated_by", "updated_at"]
    inlines = [LogSubscriptionItemInline]
    save_as = False  # 暂时禁用"另存为"功能，避免复杂的校验逻辑问题

    fieldsets = (
        (None, {"fields": ("name", "token", "is_enabled")}),
        (_("描述"), {"fields": ("description",)}),
        (
            _("审计信息"),
            {"fields": ("created_by", "created_at", "updated_by", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_urls(self):
        """添加自定义 URL"""
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
        """SQL 预览和调试界面"""
        subscription = self.get_object(request, object_id)
        if not subscription:
            change_url = reverse(f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist")
            return TemplateResponse(
                request,
                "admin/log_subscription/preview_sql.html",
                {
                    **self.admin_site.each_context(request),
                    "opts": self.model._meta,
                    "title": _("订阅不存在"),
                    "api_url": "/api/v1/log_subscription/log_subscription/query/",
                    "original": None,
                    "initial": self._default_preview_initial(),
                    "back_url": change_url,
                    "data_sources": [],
                },
            )

        # 获取订阅关联的所有数据源
        data_sources = []
        seen_source_ids = set()
        for item in subscription.items.all():
            for source in item.data_sources.all():
                if source.source_id not in seen_source_ids:
                    data_sources.append({"id": source.source_id, "name": source.name})
                    seen_source_ids.add(source.source_id)

        change_url = reverse(
            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
            args=[subscription.pk],
        )
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": subscription,
            "title": _("调试订阅 - {name}").format(name=str(subscription)),
            "api_url": "/api/v1/log_subscription/log_subscription/query/",
            "initial": self._default_preview_initial(),
            "back_url": request.GET.get("next") or change_url,
            "data_sources": data_sources,
        }
        return TemplateResponse(request, "admin/log_subscription/preview_sql.html", context)

    def _default_preview_initial(self):
        """默认的预览参数"""
        now = timezone.localtime()
        return {
            "start_time": now - datetime.timedelta(hours=1),
            "end_time": now,
            "page": 1,
            "page_size": 10,
        }

    def get_items_count(self, obj):
        """获取配置项数量"""
        return obj.items.count()

    get_items_count.short_description = _("配置项数量")

    def save_model(self, request, obj, form, change):
        """保存模型"""
        # 如果是"另存为"操作，生成新的 token
        if "_saveasnew" in request.POST:
            obj.token = uuid.uuid4().hex
            obj.pk = None

        super().save_model(request, obj, form, change)


@admin.register(LogSubscriptionItem)
class LogSubscriptionItemAdmin(admin.ModelAdmin):
    """日志订阅配置项管理"""

    form = LogSubscriptionItemAdminForm

    list_display = ["subscription", "name", "description", "get_data_sources_display", "order"]
    list_filter = ["subscription"]
    search_fields = ["name", "description"]
    filter_horizontal = ["data_sources"]
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]

    fieldsets = (
        (None, {"fields": ("subscription", "name", "order")}),
        (_("数据源"), {"fields": ("data_sources",), "description": _("选择一个或多个数据源")}),
        (
            _("筛选条件"),
            {
                "fields": ("condition",),
                "description": _("配置筛选条件，必须包含所有数据源的必须筛选字段。<br>" "注意: field.table 在配置时给默认值即可（如 't'），查询时会被自动替换为实际表别名。"),
            },
        ),
        (_("描述"), {"fields": ("description",)}),
        (
            _("审计信息"),
            {"fields": ("created_by", "created_at", "updated_by", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_data_sources_display(self, obj):
        """显示数据源列表"""
        sources = obj.data_sources.all()
        return ", ".join([s.name for s in sources]) if sources else "-"

    get_data_sources_display.short_description = _("数据源")

    def save_model(self, request, obj, form, change):
        """保存模型后验证必须筛选字段"""
        super().save_model(request, obj, form, change)

        # 保存 ManyToMany 关系
        form.save_m2m()
