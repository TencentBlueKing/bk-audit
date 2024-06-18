from typing import Dict

from apps.notice.constants import MsgType
from apps.notice.senders.mail import MailSender
from apps.notice.senders.rtx import RTXSender
from apps.notice.senders.sms import SMSSender
from apps.notice.senders.voice import VoiceSender
from apps.notice.senders.weixin import WeixinSender

SENDERS: Dict = {
    MsgType.RTX: RTXSender,
    MsgType.MAIL: MailSender,
    MsgType.SMS: SMSSender,
    MsgType.VOICE: VoiceSender,
    MsgType.WEIXIN: WeixinSender,
}

__all__ = [
    "SENDERS",
]
