# -*- coding: utf-8 -*-
"""
Risk event subscription resources.
"""
import abc

from bk_resource import api
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from services.web.risk.exceptions import RiskEventSubscriptionNotFound
from services.web.risk.handlers.subscription_sql import RiskEventSubscriptionSQLBuilder
from services.web.risk.models import RiskEventSubscription
from services.web.risk.serializers import (
    RiskEventSubscriptionQueryResponseSerializer,
    RiskEventSubscriptionQuerySerializer,
)


class RiskEventSubscriptionMeta(AuditMixinResource, abc.ABC):
    tags = ["RiskEventSubscription"]
    audit_action = None
    audit_resource_type = None


class QueryRiskEventSubscription(RiskEventSubscriptionMeta):
    name = gettext_lazy("风险事件订阅查询")
    RequestSerializer = RiskEventSubscriptionQuerySerializer
    ResponseSerializer = RiskEventSubscriptionQueryResponseSerializer

    def perform_request(self, validated_request_data):
        subscription = self._get_subscription(validated_request_data["token"])
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        builder = RiskEventSubscriptionSQLBuilder(
            namespace=subscription.namespace,
            time_range=(start_time, end_time),
            subscription_condition=subscription.get_where_condition(),
        )
        limit = page_size
        offset = page_size * (page - 1)
        query_sql = builder.build_query_sql(limit=limit, offset=offset)
        count_sql = builder.build_count_sql()
        response = {
            "page": page,
            "page_size": page_size,
            "total": 0,
            "results": [],
            "query_sql": query_sql,
            "count_sql": count_sql,
        }
        if validated_request_data.get("raw"):
            return response

        data_resp, count_resp = api.bk_base.query_sync.bulk_request(
            [
                {"sql": query_sql},
                {"sql": count_sql},
            ]
        )
        results = data_resp.get("list", [])
        count_list = count_resp.get("list", [])
        response["results"] = results
        response["total"] = count_list[0].get("count", 0) if count_list else 0
        return response

    def _get_subscription(self, token: str) -> RiskEventSubscription:
        """
        根据 token 拉取启用状态的订阅配置，若不存在则抛出 RiskEventSubscriptionNotFound。

        该方法负责完成最小的鉴权（依赖 token）以及封装异常，方便资源层统一返回 404。
        """
        subscription = RiskEventSubscription.objects.filter(token=token, is_enabled=True).first()
        if not subscription:
            raise RiskEventSubscriptionNotFound()
        return subscription
