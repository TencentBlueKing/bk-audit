import abc
from typing import Callable, Optional, Tuple

from apps.notice.models import NoticeButton, NoticeContent, NoticeLogV2

BUILD_RESPONSE_T = Tuple[str, NoticeContent, Optional[NoticeButton], dict]


class Builder:
    """
    消息内容构造器
    """

    def __init__(self, notice_log: NoticeLogV2, need_agg: bool, agg_count: int) -> None:
        self.notice_log = notice_log
        self.relate_id = self.notice_log.relate_id
        self.need_agg = need_agg
        self.agg_count = agg_count

    def build_msg(self, msg_type: str) -> BUILD_RESPONSE_T:
        _builder: Callable[[], BUILD_RESPONSE_T] = getattr(self, f"build_{msg_type}")
        return _builder()

    @abc.abstractmethod
    def build_mail(self) -> BUILD_RESPONSE_T:
        raise NotImplementedError()

    @abc.abstractmethod
    def build_rtx(self) -> BUILD_RESPONSE_T:
        raise NotImplementedError()

    @abc.abstractmethod
    def build_sms(self) -> BUILD_RESPONSE_T:
        raise NotImplementedError()

    @abc.abstractmethod
    def build_voice(self) -> BUILD_RESPONSE_T:
        raise NotImplementedError()

    @abc.abstractmethod
    def build_weixin(self) -> BUILD_RESPONSE_T:
        raise NotImplementedError()
