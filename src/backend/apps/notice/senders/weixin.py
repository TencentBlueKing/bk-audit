from bk_resource import api

from apps.notice.senders.base import Sender


class WeixinSender(Sender):
    """
    发送微信消息
    """

    api_resource = api.bk_cmsi.send_weixin

    def _build_params(self) -> dict:
        return {
            "receiver__username": self.receivers,
            "data": {
                "heading": self.title,
                "message": self.content.to_string(),
                **self.configs,
            },
        }
