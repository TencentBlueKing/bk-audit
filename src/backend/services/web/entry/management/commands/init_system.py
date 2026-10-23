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

from django.core.management.base import BaseCommand, CommandError

from apps.exceptions import InitSystemDisabled
from services.web.entry.init.base import SystemInitHandler


class Command(BaseCommand):
    def handle(self, **kwargs):
        try:
            if not SystemInitHandler().init():
                # 初始化未完成时返回非零退出码（CommandError 默认 return code=1）
                # 中断 pre_release_hook 的 && 链，避免把未完成的迁移当作发布成功
                raise CommandError("[InitSystem] Unfinished: 系统初始化未完成，禁止发布")
        # 只处理未开启系统初始化的异常情况，其他异常情况直接终止初始化
        except InitSystemDisabled as err:
            print(str(err))
