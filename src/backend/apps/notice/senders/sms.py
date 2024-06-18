from bk_resource import api

from apps.notice.constants import MsgType
from apps.notice.senders.base import Sender


class SMSSender(Sender):
    """
    发送短信消息
    """

    api_resource = api.bk_cmsi.send_msg

    def _build_params(self) -> dict:
        return {
            "msg_type": MsgType.SMS.value,
            "receiver__username": self.receivers,
            "title": self.title,
            "content": self.content.to_string(),
            **self.configs,
        }
