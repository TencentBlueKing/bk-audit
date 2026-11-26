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
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.entry.init.base import SystemInitHandler
from services.web.entry.init.deploy_storage import validate_deployment
from services.web.entry.init.v4_wait import BKBaseV4InitTimeout


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="按部署声明初始化，失败不放行")
        parser.add_argument("--check-only", action="store_true", help="只校验配置，不读数据库或调用平台")
        parser.add_argument("--phase", choices=("bootstrap", "finalize"), help="严格初始化阶段")

    def handle(self, **kwargs):
        try:
            if kwargs["check_only"] or kwargs["phase"]:
                if not kwargs["strict"]:
                    raise CommandError("--check-only/--phase requires --strict")
            if kwargs["strict"]:
                deployment = validate_deployment()
                if kwargs["check_only"]:
                    self.stdout.write("[InitSystem] 部署声明检查通过，尚未验证平台可用性")
                    return
                if not kwargs["phase"]:
                    raise CommandError("--strict requires --phase bootstrap/finalize")
                SystemInitHandler().init_strict(kwargs["phase"], deployment)
                return
            if not SystemInitHandler().init():
                # 初始化未完成时返回非零退出码（CommandError 默认 return code=1）
                # 中断 pre_release_hook 的 && 链，避免把未完成的迁移当作发布成功
                raise CommandError("[InitSystem] Unfinished: 系统初始化未完成，禁止发布")
        except (BKBaseV4InitTimeout, BKBaseResourceMappingError) as err:
            raise CommandError(str(err)) from None
        # 只处理未开启系统初始化的异常情况，其他异常情况直接终止初始化
        except InitSystemDisabled as err:
            print(str(err))
