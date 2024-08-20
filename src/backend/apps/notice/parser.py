# -*- coding: utf-8 -*-
from typing import Union

from bk_resource import resource

from apps.notice.constants import MemberVariable


class MemberVariableParser:
    """
    成员变量解析器
    """

    def __init__(self, operator: str):
        """
        :param operator: 责任人
        """
        self.operator = operator

    def handle(self, member: Union[str, MemberVariable]) -> str:
        match member:
            case MemberVariable.OPERATOR:
                return self.operator
            case MemberVariable.OPERATOR_SUPERIOR:
                return resource.user_manage.retrieve_leader(id=self.operator)
        return member
