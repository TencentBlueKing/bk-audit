from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.settings import api_settings

from apps.meta.utils.saas import get_saas_url
from apps.notice.builders.base import BUILD_RESPONSE_T, Builder
from apps.notice.models import NoticeButton, NoticeContent, NoticeContentConfig

try:
    from services.web.risk.constants import EventMappingFields
    from services.web.risk.models import Risk
    from services.web.strategy_v2.models import Strategy
except ImportError:
    pass


class RiskBuilder(Builder):
    """
    风险通知构造器
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.risk = Risk.objects.filter(risk_id=self.relate_id).first()
        if self.risk is None:
            self.strategy = None
        else:
            self.strategy = Strategy.objects.filter(strategy_id=self.risk.strategy_id).first()

    def build_msg(self, *args, **kwargs) -> BUILD_RESPONSE_T:
        # 构造标题
        title = self.notice_log.title

        # 构造内容
        risk_time = self.risk.event_time.astimezone(timezone.get_current_timezone())
        risk_url = "{}/risk-manage/detail/{}".format(get_saas_url(settings.APP_CODE), self.risk.risk_id)

        # 聚合增加内容
        if self.need_agg:
            if "待办" in title or "Pending" in title:
                value = gettext("您有共%d条风险待处理，请及时前往审计中心查看处理，以下为其中1个风险信息") % self.agg_count
            else:
                value = gettext("发现共%d条新风险，请点击前往审计中心查看详情，以下为其中1个风险信息") % self.agg_count
            notice_contents = [NoticeContentConfig(key="notice_info", name="", value=value)]
        else:
            notice_contents = []

        # 消息主要内容
        notice_contents.extend(
            [
                NoticeContentConfig(
                    key="risk_id", name=gettext("Risk ID"), value=f'<a href="{risk_url}">{self.risk.risk_id}</a>'
                ),
                NoticeContentConfig(
                    key=EventMappingFields.EVENT_CONTENT.field_name,
                    name=gettext("风险描述"),
                    value=self.risk.event_content or "- -",
                ),
                NoticeContentConfig(
                    key="strategy",
                    name=gettext("命中策略"),
                    value=f"{self.strategy.strategy_name}({self.strategy.strategy_id})",
                ),
                NoticeContentConfig(
                    key=EventMappingFields.OPERATOR.field_name,
                    name=gettext("责任人"),
                    value="; ".join(self.risk.operator if isinstance(self.risk.operator, list) else []) or "- -",
                ),
                NoticeContentConfig(
                    key=EventMappingFields.EVENT_TIME.field_name,
                    name=gettext("风险发现时间"),
                    value=risk_time.strftime(api_settings.DATETIME_FORMAT),
                ),
            ]
        )
        content = NoticeContent(*notice_contents)

        button = NoticeButton(text=gettext("Show Detail"), url=risk_url)

        return title, content, button, {}

    def build_mail(self) -> BUILD_RESPONSE_T:
        pass

    def build_rtx(self) -> BUILD_RESPONSE_T:
        pass

    def build_sms(self) -> BUILD_RESPONSE_T:
        pass

    def build_voice(self) -> BUILD_RESPONSE_T:
        pass

    def build_weixin(self) -> BUILD_RESPONSE_T:
        pass
