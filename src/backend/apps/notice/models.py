# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from bk_audit.log.models import AuditInstance
from bk_resource.utils.common_utils import get_md5
from django.db import models
from django.utils.translation import gettext_lazy

from core.models import OperateRecordModel, SoftDeleteModel


class NoticeContentConfig:
    """
    通知内容配置
    """

    def __init__(self, key: str, name: str, value: str):
        self.key = key
        self.display_name = name
        self.value = value


class NoticeContent:
    """
    通知内容
    """

    def __init__(self, *content_configs: NoticeContentConfig):
        self.content_configs = content_configs

    def to_string(self) -> str:
        data = [
            "{}: {}".format(content_config.display_name, content_config.value)
            for content_config in self.content_configs
        ]
        return "\n".join(data)


class NoticeButton:
    """
    通知按钮
    """

    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url


class NoticeGroupAuditInstance(AuditInstance):
    """
    审计实例 - 通知组
    """

    def __init__(self, instance: "NoticeGroup"):
        super().__init__(instance=instance)
        self.instance = instance

    @property
    def instance_id(self):
        return self.instance.group_id

    @property
    def instance_name(self):
        return self.instance.group_name

    @property
    def instance_data(self):
        from apps.notice.serializers import NoticeGroupInfoSerializer

        return NoticeGroupInfoSerializer(self.instance).data


class NoticeGroup(SoftDeleteModel):
    """
    通知组
    """

    group_id = models.BigAutoField(gettext_lazy("通知组ID"), primary_key=True)
    group_name = models.CharField(gettext_lazy("通知组名称"), max_length=64, db_index=True)
    group_member = models.JSONField(gettext_lazy("通知组成员"), default=list)
    notice_config = models.JSONField(gettext_lazy("通知配置"), default=list)
    description = models.TextField(gettext_lazy("描述"), null=True, blank=True)

    class Meta:
        verbose_name = gettext_lazy("通知组")
        verbose_name_plural = verbose_name
        ordering = ["-group_id"]

    @property
    def audit_instance(self):
        return NoticeGroupAuditInstance(self)


class NoticeLog(OperateRecordModel):
    """
    消息记录
    """

    log_id = models.BigAutoField(gettext_lazy("ID"), primary_key=True)
    msg_type = models.CharField(gettext_lazy("发送方式"), max_length=255)
    title = models.TextField(gettext_lazy("标题"), null=True, blank=True)
    content = models.TextField(gettext_lazy("内容"), null=True, blank=True)
    md5 = models.CharField(gettext_lazy("消息Hash值"), max_length=255)
    receivers = models.JSONField(gettext_lazy("收件人"), null=True, blank=True)
    send_at = models.BigIntegerField(gettext_lazy("发送时间"))
    trace_id = models.CharField(gettext_lazy("Trace ID"), null=True, blank=True, max_length=255)
    is_success = models.BooleanField(gettext_lazy("是否成功"), default=False)
    is_duplicate = models.BooleanField(gettext_lazy("是否重复"), default=False)
    extra = models.TextField(gettext_lazy("拓展信息"), null=True, blank=True)

    class Meta:
        verbose_name = gettext_lazy("消息记录")
        verbose_name_plural = verbose_name
        ordering = ["-log_id"]
        index_together = [["md5", "send_at"]]

    @classmethod
    def build_hash(cls, receivers: list, msg_type: str, title: str, content: NoticeContent) -> str:
        return get_md5({"receiver": receivers, "msg_type": msg_type, "title": title, "content": content.to_string()})
