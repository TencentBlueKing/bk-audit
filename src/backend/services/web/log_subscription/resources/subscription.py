# -*- coding: utf-8 -*-
"""
Log subscription resources.
"""
import abc
import uuid
from typing import List, Optional, Union

from bk_resource import api
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy
from pydantic import ValidationError as PydanticValidationError
from pypika.enums import Order as PypikaOrder

from apps.audit.resources import AuditMixinResource
from core.sql.builder.builder import BKBaseQueryBuilder
from core.sql.builder.generator import BkBaseComputeSqlGenerator
from core.sql.constants import FieldType, FilterConnector, Operator
from core.sql.model import (
    Condition,
    Field,
    Order,
    Pagination,
    SqlConfig,
    Table,
    WhereCondition,
)
from services.web.log_subscription.exceptions import (
    DataSourceNotFound,
    DataSourceNotInSubscription,
    LogSubscriptionNotFound,
)
from services.web.log_subscription.models import LogDataSource, LogSubscription
from services.web.log_subscription.serializers import (
    LogSubscriptionQueryResponseSerializer,
    LogSubscriptionQuerySerializer,
)


class LogSubscriptionMeta(AuditMixinResource, abc.ABC):
    """日志订阅资源基类"""

    tags = ["LogSubscription"]
    audit_action = None
    audit_resource_type = None


class QueryLogSubscription(LogSubscriptionMeta):
    """
    日志订阅查询接口

    根据 token 和数据源标识查询日志数据。
    """

    name = gettext_lazy("日志订阅查询")
    RequestSerializer = LogSubscriptionQuerySerializer
    ResponseSerializer = LogSubscriptionQueryResponseSerializer

    def perform_request(self, validated_request_data):
        """
        执行查询请求

        流程:
        1. 验证 token，获取订阅配置
        2. 验证 source_id，获取数据源
        3. 组装完整的查询条件（时间 + 订阅条件 + 自定义条件）
        4. 使用 BkBaseComputeSqlGenerator 构建 SQL
        5. 执行查询并返回分页结果
        """
        # 1. 获取订阅配置
        subscription = self._get_subscription(validated_request_data["token"])

        # 2. 获取数据源
        source_id = validated_request_data["source_id"]
        data_source = self._get_data_source(subscription, source_id)

        # 3. 组装完整的查询条件
        where_condition = self._build_where_condition(
            data_source=data_source,
            subscription=subscription,
            source_id=source_id,
            start_time=validated_request_data["start_time"],
            end_time=validated_request_data["end_time"],
            custom_filters=validated_request_data.get("filters"),
        )

        # 4. 构建 SqlConfig
        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        select_fields = self._build_select_fields(
            data_source=data_source,
            custom_fields=validated_request_data.get("fields"),
        )

        sql_config = SqlConfig(
            from_table=Table(table_name=data_source.get_table_name()),
            select_fields=select_fields,  # 为空时使用 SELECT *
            where=where_condition,
            order_by=[
                Order(
                    field=Field(
                        table=data_source.get_table_name(),
                        raw_name=data_source.time_field,
                        display_name=data_source.time_field,
                        field_type=FieldType.LONG,
                    ),
                    order=PypikaOrder.desc,
                )
            ],
            pagination=Pagination(limit=page_size, offset=page_size * (page - 1)),
        )

        # 5. 生成 SQL
        generator = BkBaseComputeSqlGenerator(BKBaseQueryBuilder())
        query_sql = str(generator.generate(sql_config))
        count_sql = str(generator.generate_count(sql_config))

        # 构造响应
        response = {
            "page": page,
            "page_size": page_size,
            "total": 0,
            "results": [],
            "query_sql": query_sql,
            "count_sql": count_sql,
        }

        # 如果只需要 SQL，直接返回
        if validated_request_data.get("raw"):
            return response

        # 6. 执行查询
        data_resp, count_resp = api.bk_base.query_sync.bulk_request([{"sql": query_sql}, {"sql": count_sql}])

        results = data_resp.get("list", [])
        count_list = count_resp.get("list", [])

        response["results"] = results
        response["total"] = count_list[0].get("count", 0) if count_list else 0

        return response

    def _get_subscription(self, token: Union[str, uuid.UUID]) -> LogSubscription:
        """
        获取启用的订阅配置

        Args:
            token: 订阅 Token (UUID 对象或字符串)

        Returns:
            订阅配置对象

        Raises:
            LogSubscriptionNotFound: 订阅不存在或未启用
        """
        # 注意：Serializer 会把 token 转换为 UUID 对象，但数据库中存储的是 hex 格式字符串（无连字符）
        # 需要转换为 hex 格式
        if isinstance(token, uuid.UUID):
            token = token.hex

        # LogSubscription 使用 SoftDeleteModel，objects manager 会自动过滤 is_deleted=True
        subscription = (
            LogSubscription.objects.filter(token=token, is_enabled=True).prefetch_related("items__data_sources").first()
        )

        if not subscription:
            raise LogSubscriptionNotFound()

        return subscription

    def _get_data_source(self, subscription: LogSubscription, source_id: str) -> LogDataSource:
        """
        获取数据源并验证其在订阅配置中

        Args:
            subscription: 订阅配置
            source_id: 数据源标识

        Returns:
            数据源对象

        Raises:
            DataSourceNotFound: 数据源不存在或未启用
            DataSourceNotInSubscription: 数据源不在订阅配置中
        """
        # 查找数据源
        data_source = LogDataSource.objects.filter(source_id=source_id, is_enabled=True).first()

        if not data_source:
            raise DataSourceNotFound(source_id)

        # 验证该数据源是否在订阅配置的某个配置项中
        has_source = subscription.items.filter(data_sources=data_source).exists()

        if not has_source:
            raise DataSourceNotInSubscription(source_id)

        return data_source

    def _get_subscription_condition(self, subscription: LogSubscription, source_id: str) -> Optional[WhereCondition]:
        """
        获取订阅配置中针对该数据源的筛选条件

        如果多个配置项都包含该数据源，使用 OR 连接。

        Args:
            subscription: 订阅配置
            source_id: 数据源标识

        Returns:
            筛选条件对象，如果没有配置项包含该数据源则返回 None
        """
        # 查找所有包含该数据源的配置项
        items = subscription.items.filter(data_sources__source_id=source_id).all()

        if not items:
            return None

        # 收集所有配置项的条件
        conditions = []
        for item in items:
            condition = item.get_where_condition()
            if condition:
                conditions.append(condition)

        if not conditions:
            return None

        # 如果只有一个条件，直接返回
        if len(conditions) == 1:
            return conditions[0]

        # 多个条件用 OR 连接
        return WhereCondition(connector=FilterConnector.OR, conditions=conditions)

    def _parse_custom_condition(self, filters: Optional[dict]) -> Optional[WhereCondition]:
        """
        解析用户传入的自定义筛选条件

        Args:
            filters: WhereCondition 格式的字典

        Returns:
            筛选条件对象

        Raises:
            ValidationError: 条件格式不正确
        """
        if not filters:
            return None

        try:
            return WhereCondition.model_validate(filters)
        except PydanticValidationError as exc:
            raise ValidationError({"filters": str(exc)})

    def _replace_table_name(self, condition: WhereCondition, table_name: str) -> None:
        """
        递归替换 WhereCondition 中所有 Field 的 table 名称（原地修改）

        Args:
            condition: 条件对象（会被原地修改）
            table_name: 目标表名
        """
        # 如果是叶子节点（包含 condition 字段）
        if condition.condition and condition.condition.field:
            # 直接修改 field 的 table 属性
            condition.condition.field.table = table_name

        # 如果是组合节点（包含 conditions 列表），递归处理每个子条件
        if condition.conditions:
            for sub_condition in condition.conditions:
                self._replace_table_name(sub_condition, table_name)

    def _build_where_condition(
        self,
        data_source: LogDataSource,
        subscription: LogSubscription,
        source_id: str,
        start_time: int,
        end_time: int,
        custom_filters: Optional[dict] = None,
    ) -> WhereCondition:
        """
        组装完整的 WHERE 条件

        将时间范围、订阅条件、自定义条件组合成一个 WhereCondition 对象。

        Args:
            data_source: 数据源对象
            subscription: 订阅配置
            source_id: 数据源标识
            start_time: 开始时间（毫秒）
            end_time: 结束时间（毫秒）
            custom_filters: 自定义筛选条件

        Returns:
            完整的查询条件对象
        """
        conditions = []
        table_name = data_source.get_table_name()

        # 1. 添加时间范围条件（表名已经是正确的）
        time_condition = WhereCondition(
            condition=Condition(
                field=Field(
                    table=table_name,
                    raw_name=data_source.time_field,
                    display_name=data_source.time_field,
                    field_type=FieldType.LONG,
                ),
                operator=Operator.BETWEEN,
                filters=[start_time, end_time],
            )
        )
        conditions.append(time_condition)

        # 2. 添加订阅配置的筛选条件
        subscription_condition = self._get_subscription_condition(subscription, source_id)
        if subscription_condition:
            conditions.append(subscription_condition)

        # 3. 添加自定义筛选条件
        custom_condition = self._parse_custom_condition(custom_filters)
        if custom_condition:
            conditions.append(custom_condition)

        # 4. 组合所有条件（使用 AND 连接）
        if len(conditions) == 1:
            final_condition = conditions[0]
        else:
            final_condition = WhereCondition(connector=FilterConnector.AND, conditions=conditions)

        # 5. 统一替换所有条件中的表名占位符 't' 为实际表名
        self._replace_table_name(final_condition, table_name)

        return final_condition

    def _build_select_fields(
        self, data_source: LogDataSource, custom_fields: Optional[List[str]] = None
    ) -> List[Field]:
        """
        构建 SELECT 字段列表

        Args:
            data_source: 数据源对象
            custom_fields: 自定义字段列表

        Returns:
            Field 对象列表，为空时表示 SELECT *
        """
        if not custom_fields:
            return []  # 空列表表示 SELECT *

        # 构建 Field 对象列表
        return [
            Field(
                table=data_source.get_table_name(),
                raw_name=field_name,
                display_name=field_name,
                field_type=FieldType.STRING,  # 默认字符串类型，实际类型由 Doris 决定
            )
            for field_name in custom_fields
        ]
