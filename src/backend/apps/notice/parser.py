# -*- coding: utf-8 -*-
import abc
from typing import List, Union

from bk_resource import resource
from django.db.models import QuerySet

from apps.notice.constants import MemberVariable
from apps.notice.models import NoticeGroup


class MemberVariableParserBase(abc.ABC):
    def is_skip(self, member: str) -> bool:
        """默认跳过变量"""
        return MemberVariable.match(member) is not None

    @abc.abstractmethod
    def parse_member(self, member: Union[str, MemberVariable]) -> List[str]:
        """解析成员"""
        raise NotImplementedError()

    def parse_group(self, group: NoticeGroup) -> List[str]:
        """
        处理组成员
        """

        parsed_members = set()
        for member in group.group_member:
            if self.is_skip(member):
                continue
            members = {_member for _member in self.parse_member(member) if _member}
            parsed_members.update(members)
        return list(parsed_members)

    def parse_groups(self, groups: Union[QuerySet["NoticeGroup"], List["NoticeGroup"]]) -> List[str]:
        """
        解析处理组成员
        """

        return list({member for group in groups for member in self.parse_group(group)})


class MemberVariableParser(MemberVariableParserBase):
    """
    成员变量解析器
    """

    def __init__(self, operators: List[str]):
        """
        :param operators: 责任人
        """

        self.operators = operators

    def parse_member(self, member: Union[str, MemberVariable]) -> List[str]:
        match member:
            case MemberVariable.OPERATOR:
                return self.operators
            case MemberVariable.OPERATOR_LEADER:
                return [resource.user_manage.retrieve_leader(bk_username=operator) for operator in self.operators]
        return [member]


class IgnoreMemberVariableParser(MemberVariableParserBase):
    """
    忽略成员变量解析器
    """

    def parse_member(self, member: Union[str, MemberVariable]) -> List[str]:
        return [member]
