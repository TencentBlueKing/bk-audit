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
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import datetime

from blueapps.utils.logger import logger
from django.core.management.base import BaseCommand, CommandError

from services.web.risk.models import Risk


class Command(BaseCommand):
    """批量软删除指定策略与时间范围的风险单

    典型用法（产品首次应用：策略 129/131 从 2025-07-03 起的风险单软删除）：
        # 先 dry-run 确认匹配数量
        python manage.py soft_delete_risks --strategy-ids 129,131 --start-date 2025-07-03 --dry-run
        # 确认后执行
        python manage.py soft_delete_risks --strategy-ids 129,131 --start-date 2025-07-03
    """

    help = "批量软删除指定策略和时间范围的风险单"

    def add_arguments(self, parser):
        parser.add_argument(
            "--strategy-ids",
            type=str,
            required=True,
            help="策略ID列表，逗号分隔，如 129,131",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            required=True,
            help="起始日期（含），格式 YYYY-MM-DD，如 2025-07-03",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            default=None,
            help="结束日期（含），格式 YYYY-MM-DD，默认至今",
        )
        parser.add_argument("--dry-run", action="store_true", help="只统计匹配数量，不执行删除")

    def handle(self, *args, **options):
        # 解析策略 ID
        try:
            strategy_ids = [int(s.strip()) for s in options["strategy_ids"].split(",") if s.strip()]
        except ValueError:
            raise CommandError("--strategy-ids 必须为逗号分隔的整数列表")

        if not strategy_ids:
            raise CommandError("--strategy-ids 不能为空")

        # 解析日期
        try:
            start_date = datetime.datetime.strptime(options["start_date"], "%Y-%m-%d")
        except ValueError:
            raise CommandError("--start-date 格式必须为 YYYY-MM-DD")

        end_date_str = options["end_date"]
        if end_date_str:
            try:
                # 结束日期含当天，故上界推到次日 00:00
                end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d") + datetime.timedelta(days=1)
            except ValueError:
                raise CommandError("--end-date 格式必须为 YYYY-MM-DD")
        else:
            end_date = None

        # 构造查询：objects 自动过滤 is_deleted=False，避免重复软删除已删除记录
        qs = Risk.objects.filter(strategy_id__in=strategy_ids, event_time__gte=start_date)
        if end_date:
            qs = qs.filter(event_time__lt=end_date)

        count = qs.count()
        self.stdout.write(
            f"匹配到 {count} 条风险单（策略: {strategy_ids}, "
            f"起始: {start_date.date()}, 结束: {end_date_str or '至今'}）"
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("（dry-run 模式，不执行删除）"))
            return

        if count == 0:
            self.stdout.write("无匹配记录，退出")
            return

        # 批量软删除：SoftDeleteQuerySet.delete → UPDATE is_deleted=True
        deleted, _ = qs.delete()
        logger.info(
            "[soft_delete_risks] strategy_ids=%s start=%s end=%s deleted=%s",
            strategy_ids,
            start_date.date(),
            end_date_str or "now",
            deleted,
        )
        self.stdout.write(self.style.SUCCESS(f"成功软删除 {deleted} 条风险单"))
