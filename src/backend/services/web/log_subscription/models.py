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

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.utils.translation import gettext_lazy
from pydantic import ValidationError as PydanticValidationError

from api.bk_base.constants import StorageType
from core.models import OperateRecordModel, SoftDeleteModel, UUIDField
from core.sql.model import WhereCondition
from services.web.query.constants import TIMESTAMP_PARTITION_FIELD


class LogDataSource(OperateRecordModel):
    """
    日志数据源配置

    不使用软删除，通过 is_enabled 控制启用状态。
    source_id 作为唯一标识，不会与软删除冲突。
    """

    # 数据源唯一标识
    source_id = models.CharField(
        gettext_lazy("数据源标识"),
        max_length=64,
        unique=True,
        db_index=True,
        help_text=gettext_lazy("英文标识，如 audit_log, operation_log"),
    )

    # 数据源名称
    name = models.CharField(gettext_lazy("数据源名称"), max_length=128)

    # 数据源描述
    description = models.TextField(gettext_lazy("描述"), blank=True, default="")

    # 命名空间
    namespace = models.CharField(
        gettext_lazy("命名空间"),
        max_length=64,
        default=settings.DEFAULT_NAMESPACE,
        db_index=True,
    )

    # BKBase 表 ID（直接存储，不通过 GlobalMetaConfig）
    bkbase_table_id = models.CharField(
        gettext_lazy("BKBase 表 ID"),
        max_length=255,
        help_text=gettext_lazy("BKBase 结果表 ID，如 591_bkaudit_event"),
    )

    # 存储类型
    storage_type = models.CharField(
        gettext_lazy("存储类型"),
        max_length=32,
        choices=StorageType.choices,
        default=StorageType.DORIS.value,
        help_text=gettext_lazy("BKBase 存储类型"),
    )

    # 必须筛选字段
    # 只校验字段名是否在筛选条件中，不校验字段是否真实存在于表中
    required_filter_fields = models.JSONField(
        gettext_lazy("必须筛选字段"),
        default=list,
        blank=True,
        help_text=gettext_lazy("订阅配置项选择此数据源时，筛选条件中必须包含的字段列表，如 ['system_id', 'namespace']"),
    )

    # 时间字段（使用常量）
    time_field = models.CharField(
        gettext_lazy("时间字段"),
        max_length=64,
        default=TIMESTAMP_PARTITION_FIELD,
        help_text=gettext_lazy("用于时间范围筛选的字段名"),
    )

    # 允许返回的字段列表（可选，为空则返回所有字段）
    fields = models.JSONField(
        gettext_lazy("允许返回的字段"),
        default=list,
        blank=True,
        help_text=gettext_lazy("限制数据源允许返回的字段列表，为空则返回所有字段(*)"),
    )

    # 是否启用
    is_enabled = models.BooleanField(gettext_lazy("是否启用"), default=True)

    class Meta:
        verbose_name = gettext_lazy("日志数据源")
        verbose_name_plural = verbose_name
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name}({self.source_id})"

    def get_table_name(self) -> str:
        """
        获取带存储后缀的完整表名

        Returns:
            完整表名，如 "591_bkaudit_event.doris"
        """
        return f"{self.bkbase_table_id}.{self.storage_type}"

    def validate_required_fields(self, condition: WhereCondition | None) -> bool:
        """
        验证筛选条件是否包含所有必须筛选字段

        注意：这里只校验字段名是否在筛选条件中出现，不校验字段是否真实存在于表中。
        字段是否存在交由 SQL 查询时数据库校验。

        Args:
            condition: 筛选条件对象

        Returns:
            True 表示验证通过

        Raises:
            DjangoValidationError: 缺少必须筛选字段时抛出
        """
        # 如果数据源没有必须筛选字段要求，直接通过
        if not self.required_filter_fields:
            return True

        # 如果有必须筛选字段要求，但没有提供筛选条件，则验证失败
        if not condition:
            raise DjangoValidationError(
                {
                    "condition": [
                        gettext_lazy("数据源 {source} 要求配置筛选条件，必须筛选字段: {fields}").format(
                            source=self.name, fields=", ".join(self.required_filter_fields)
                        )
                    ]
                }
            )

        # 从条件中提取所有字段名
        condition_fields = self._extract_fields_from_condition(condition)

        # 检查必须筛选字段是否都存在
        missing_fields = set(self.required_filter_fields) - condition_fields
        if missing_fields:
            raise DjangoValidationError(
                {
                    "condition": [
                        gettext_lazy("数据源 {source} 缺少必须筛选字段: {fields}").format(
                            source=self.name, fields=", ".join(missing_fields)
                        )
                    ]
                }
            )
        return True

    @staticmethod
    def _extract_fields_from_condition(condition: WhereCondition) -> set:
        """递归提取条件中的所有字段名"""
        fields = set()
        if condition.condition and condition.condition.field:
            fields.add(condition.condition.field.raw_name)
        for child in condition.conditions or []:
            fields.update(LogDataSource._extract_fields_from_condition(child))
        return fields


class LogSubscription(SoftDeleteModel):
    """
    日志订阅配置

    使用软删除，保留历史记录。
    一个订阅配置包含多个配置项，每个配置项对应一个或多个数据源。
    """

    # 配置名称
    name = models.CharField(gettext_lazy("配置名称"), max_length=128)

    # 配置描述
    description = models.TextField(gettext_lazy("配置描述"), blank=True, default="")

    # 订阅 Token（使用 UUIDField）
    token = UUIDField(gettext_lazy("订阅 Token"), unique=True, db_index=True)

    # 是否启用
    is_enabled = models.BooleanField(gettext_lazy("是否启用"), default=True)

    class Meta:
        verbose_name = gettext_lazy("日志订阅配置")
        verbose_name_plural = verbose_name
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name}({self.token})"

    def get_data_sources(self) -> models.QuerySet:
        """获取该订阅配置关联的所有数据源"""
        return LogDataSource.objects.filter(subscription_items__subscription=self).distinct()


class LogSubscriptionItem(OperateRecordModel):
    """
    日志订阅配置项

    不使用软删除，通过 CASCADE 关联主记录。
    每个配置项对应一个或多个数据源及其筛选条件。
    """

    # 所属订阅配置（CASCADE 删除）
    subscription = models.ForeignKey(
        LogSubscription, verbose_name=gettext_lazy("订阅配置"), on_delete=models.CASCADE, related_name="items"
    )

    # 配置项名称（不要求唯一）
    name = models.CharField(gettext_lazy("配置项名称"), max_length=128, help_text=gettext_lazy("配置项的描述性名称"))

    # 配置项描述
    description = models.TextField(gettext_lazy("描述"), blank=True, default="")

    # 关联的数据源（多对多）
    data_sources = models.ManyToManyField(
        LogDataSource,
        verbose_name=gettext_lazy("数据源"),
        related_name="subscription_items",
        help_text=gettext_lazy("选择一个或多个数据源"),
    )

    # 筛选条件（JSON 格式存储 WhereCondition）
    # field.table 在配置时给默认值即可，查询时会被重写
    condition = models.JSONField(
        gettext_lazy("筛选条件"),
        default=dict,
        blank=True,
        help_text=gettext_lazy("WhereCondition 格式的筛选条件，必须包含所有关联数据源的必须筛选字段"),
    )

    # 排序
    order = models.IntegerField(gettext_lazy("排序"), default=0)

    class Meta:
        verbose_name = gettext_lazy("日志订阅配置项")
        verbose_name_plural = verbose_name
        ordering = ["subscription", "order", "-created_at"]

    def __str__(self):
        return f"{self.subscription.name} - {self.name}"

    def get_where_condition(self) -> WhereCondition | None:
        """获取筛选条件对象"""
        if not self.condition:
            return None
        try:
            return WhereCondition.model_validate(self.condition)
        except PydanticValidationError as exc:
            raise DjangoValidationError({"condition": str(exc)})

    def validate_condition_with_sources(self):
        """
        验证筛选条件是否满足所有数据源的必须筛选字段要求

        在保存配置项时调用此方法进行校验。

        验证逻辑：
        1. 获取配置项的筛选条件
        2. 遍历配置项关联的所有数据源
        3. 对每个数据源，调用其 validate_required_fields 方法验证
        4. 如果任何一个数据源验证失败，抛出异常

        注意：只校验必须筛选字段是否在条件中，不校验字段是否真实存在。
        """
        condition = self.get_where_condition()

        # 验证所有数据源的必须筛选字段
        for source in self.data_sources.all():
            source.validate_required_fields(condition)

    def clean(self):
        """
        Django Admin 保存前的验证

        注意：此时 ManyToMany 关系可能还未保存，完整的必须筛选字段验证需要在 save() 后进行。
        这里只做基本的格式验证。
        """
        super().clean()
        # 验证筛选条件格式
        if self.condition:
            try:
                WhereCondition.model_validate(self.condition)
            except Exception as exc:
                raise DjangoValidationError({"condition": str(exc)})
