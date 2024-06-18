from bk_resource import api

from apps.notice.senders.base import Sender


class VoiceSender(Sender):
    """
    发送电话消息
    """

    api_resource = api.bk_cmsi.send_voice

    def _build_params(self) -> dict:
        return {
            "auto_read_message": self.title,
            "receiver__username": self.receivers,
            **self.configs,
        }
