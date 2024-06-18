from apps.notice.builders.base import BUILD_RESPONSE_T, Builder
from apps.notice.models import NoticeContent, NoticeContentConfig


class ErrorBuilder(Builder):
    """
    异常信息构造器
    """

    def build_msg(self, *args, **kwargs) -> BUILD_RESPONSE_T:
        content = NoticeContent(
            *[
                NoticeContentConfig(
                    key=line.split(": ", 1)[0], name=line.split(": ", 1)[0], value=line.split(": ", 1)[1]
                )
                for line in self.notice_log.content.split("\n")
                if line.find(": ") != -1
            ]
        )
        return self.notice_log.title, content, None, {}

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
