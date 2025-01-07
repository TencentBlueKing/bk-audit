# -*- coding: utf-8 -*-
from apps.notice.parser import MemberVariableParser
from services.web.risk.models import Risk


class RiskNoticeParser(MemberVariableParser):
    def is_skip(self, member: str) -> bool:
        """对所有变量进行处理"""
        return False

    def __init__(self, risk: Risk):
        super().__init__(operator=risk.operator[0] if risk.operator else "")
