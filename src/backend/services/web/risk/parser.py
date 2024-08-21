# -*- coding: utf-8 -*-
from apps.notice.parser import MemberVariableParser
from services.web.risk.models import Risk


class RiskNoticeParser(MemberVariableParser):
    def __init__(self, risk: Risk):
        super().__init__(operator=risk.operator)
