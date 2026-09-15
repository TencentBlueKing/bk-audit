# -*- coding: utf-8 -*-
from typing import List, Union

from django.db.models import QuerySet

from apps.notice.models import NoticeGroup
from apps.notice.parser import MemberVariableParser
from services.web.risk.models import Risk


class RiskNoticeParser(MemberVariableParser):
    def is_skip(self, member: str) -> bool:
        """对所有变量进行处理"""
        return False

    def __init__(self, risk: Risk):
        super().__init__(operators=risk.operator)

    def parse_groups_snapshot(
        self, groups: Union[QuerySet[NoticeGroup], List[NoticeGroup]]
    ) -> List[dict]:
        """
        快照通知组完整信息（成员解析为实际用户名）
        """
        snapshots = []
        for group in groups:
            snapshots.append(
                {
                    "group_id": group.group_id,
                    "group_name": group.group_name,
                    "group_member": self.parse_group(group),
                    "notice_config": group.notice_config,
                    "description": group.description,
                }
            )
        return snapshots
