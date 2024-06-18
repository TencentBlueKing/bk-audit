import abc
from typing import List

from bk_resource import APIResource

from apps.notice.models import NoticeButton, NoticeContent


class Sender:
    """
    发送器基类
    """

    @property
    @abc.abstractmethod
    def api_resource(self) -> APIResource:
        raise NotImplementedError()

    def __init__(
        self,
        receivers: List[str],
        title: str,
        content: NoticeContent,
        button: NoticeButton = None,
        **configs,
    ):
        self.receivers = receivers
        self.title = title
        self.content = content
        self.button = button
        self.configs = configs

    @abc.abstractmethod
    def _build_params(self) -> dict:
        raise NotImplementedError()

    def send(self) -> (bool, str):
        params = self._build_params()
        return self.api_resource(**params)
