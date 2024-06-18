from bk_resource import api

from apps.notice.senders.base import Sender


class RTXSender(Sender):
    """
    发送RTX消息
    """

    api_resource = api.bk_cmsi.send_rtx

    def _build_params(self) -> dict:
        return {
            "title": self.title,
            "receiver__username": self.receivers,
            "content": self.content.to_string(),
            **self.configs,
        }
