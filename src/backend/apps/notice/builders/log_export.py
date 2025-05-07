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
import json

from django.conf import settings
from django.utils.translation import gettext, gettext_lazy

from apps.meta.utils.saas import get_saas_url
from apps.notice.builders.base import BUILD_RESPONSE_TYPE, Builder
from apps.notice.exceptions import BuilderInitError
from apps.notice.models import NoticeButton, NoticeContent, NoticeContentConfig
from core.utils.time import mstimestamp_to_date_string
from services.web.query.models import LogExportTask

# 日志导出信息安全声明
LOG_EXPORT_SECURITY_STATEMENT = gettext_lazy(
    """信息安全声明：
    此邮件中包含导出数据，为高敏感数据资产，请遵守法律法规合规使用，如有泄露，承担相应的法律责任。
    如果您不是这封邮件的接收者，请删除邮件，并邮件告知邮件发送方。
    """
)


class LogExportBuilder(Builder):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.task: LogExportTask = LogExportTask.objects.filter(id=self.relate_id).first()
        if not self.task:
            raise BuilderInitError(err=gettext("LogExportTask %s not found") % self.relate_id)

    def build_msg(self, msg_type: str) -> BUILD_RESPONSE_TYPE:
        title = str(
            gettext("【审计中心】检索结果导出数据-%s") % mstimestamp_to_date_string(int(self.task.created_at.timestamp() * 1000))
        )
        url = "{uri}/api/v1/query/namespaces/{namespace}/collector_query_task/{id}/download/".format(
            uri=get_saas_url(settings.APP_CODE),
            namespace=self.task.namespace,
            id=self.task.id,
        )
        content_configs = [
            NoticeContentConfig(
                key="search_params",
                name=str(gettext("检索条件")),
                value=json.dumps(self.task.query_params) if self.task.query_params else "",
            ),
            NoticeContentConfig(
                key="security_statement",
                name="",
                value=str(LOG_EXPORT_SECURITY_STATEMENT),
            ),
        ]
        content = NoticeContent(*content_configs)
        button = NoticeButton(text=gettext("日志下载"), url=url)
        return title, content, button, {}

    def build_mail(self) -> BUILD_RESPONSE_TYPE:
        pass

    def build_rtx(self) -> BUILD_RESPONSE_TYPE:
        pass

    def build_sms(self) -> BUILD_RESPONSE_TYPE:
        pass

    def build_voice(self) -> BUILD_RESPONSE_TYPE:
        pass

    def build_weixin(self) -> BUILD_RESPONSE_TYPE:
        pass
