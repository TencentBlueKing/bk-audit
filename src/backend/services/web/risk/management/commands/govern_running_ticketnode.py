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
# TicketNode RUNNING 存量统计与遗留治理
#
# 统计口径：
#   1) running 总量；
#   2) 按 action / 是否该风险最新节点 / 对应 Risk.status 三维分组；
#   3) 单独给出 ForApprove/AutoProcess 且风险已 CLOSED 的数量。
#
# 治理口径（评审后执行，需显式 --apply）：
#   - 仅把「风险已关闭」的遗留 running 标记为 finished；
#   - 未关闭风险的当前审批/套餐节点保持 running；
#   - 只写 TicketNode.status，禁止改动业务库其它表；
#   - 通过 --out 落盘被修改记录，可核对、可回滚。
#
# 用法：
#   python manage.py govern_running_ticketnode                       # 只读统计
#   python manage.py govern_running_ticketnode --apply               # 治理并输出前后对比
#   python manage.py govern_running_ticketnode --apply --out /tmp/govern.json
#   python manage.py govern_running_ticketnode --skip-latest         # 跳过「是否最新节点」统计（较慢）

import json
import time

from blueapps.utils.logger import logger
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Count

from services.web.risk.constants import RiskStatus, TicketNodeStatus
from services.web.risk.handlers.ticket import AutoProcess, ForApprove
from services.web.risk.models import Risk, TicketNode

# 需要跟外部系统（ITSM / SOPS）同步状态的节点；其余节点按设计长期保持 running
DEFAULT_GOVERN_ACTIONS = [ForApprove.__name__, AutoProcess.__name__]

# 三维交叉表最多展示行数，避免输出过长
CROSS_TABLE_LIMIT = 80


class Command(BaseCommand):
    help = "TicketNode RUNNING 存量统计与遗留治理（一次性数据治理，默认只读）"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="执行清理；默认只统计，不写库")
        parser.add_argument("--out", type=str, default="", help="落盘本次被修改的节点记录（JSON），用于核对/回滚")
        parser.add_argument("--batch-size", type=int, default=500, help="每批更新条数，默认 500")
        parser.add_argument("--max-rounds", type=int, default=0, help="最大清理轮次，0 表示不限")
        parser.add_argument("--actions", type=str, default="", help="治理的 action，逗号分隔；默认审批+套餐")
        parser.add_argument("--skip-latest", action="store_true", help="跳过「是否最新节点」三维统计（全量较慢）")
        parser.add_argument("--skip-stats", action="store_true", help="跳过详细统计，只做治理与前后对比")

    def handle(self, *args, **options):
        actions = [a.strip() for a in options["actions"].split(",") if a.strip()] or DEFAULT_GOVERN_ACTIONS
        node_table = TicketNode._meta.db_table
        risk_table = Risk._meta.db_table
        placeholders = ",".join(["%s"] * len(actions))

        ctx = {
            "actions": actions,
            "placeholders": placeholders,
            "node_table": node_table,
            "risk_table": risk_table,
        }

        if not options["skip_stats"]:
            self.stats(ctx, skip_latest=options["skip_latest"])

        changed = self.clean(ctx, options["apply"], options["batch_size"], options["max_rounds"])

        if changed and options["out"]:
            self.dump_changed(changed, options["out"])

    # ------------------------------------------------------------------ 统计

    def stats(self, ctx, skip_latest=False):
        actions = ctx["actions"]
        placeholders = ctx["placeholders"]
        node_table = ctx["node_table"]
        risk_table = ctx["risk_table"]

        running = TicketNode.objects.filter(status=TicketNodeStatus.RUNNING).order_by()

        self.stdout.write("")
        self.stdout.write("=" * 72)
        self.stdout.write("TicketNode RUNNING 存量统计（只读）")
        self.stdout.write("=" * 72)

        # [A] running 总量
        total = running.count()
        self.stdout.write("[A] running 总量: %s" % total)

        # [B] 按 action 分组
        self.stdout.write("")
        self.stdout.write("[B] 按 action 分组:")
        for row in running.values("action").annotate(c=Count("id")).order_by("-c"):
            self.stdout.write("    {:<24} {}".format(row["action"], row["c"]))

        # [C] 三维交叉：action × 是否该风险最新节点 × risk.status
        if not skip_latest:
            self.stdout.write("")
            self.stdout.write("[C] 三维交叉：action × 是否该风险最新节点 × risk.status")
            self.stdout.write("    {:<24} {:<10} {:<16} {}".format("action", "is_latest", "risk.status", "count"))
            self.stdout.write("    " + "-" * 68)
            started = time.time()
            rows = self.cross_table(node_table, risk_table)
            for action, is_latest, status, count in rows[:CROSS_TABLE_LIMIT]:
                self.stdout.write(
                    "    {:<24} {:<10} {:<16} {}".format(action, is_latest, status or "<risk 不存在>", count)
                )
            if len(rows) > CROSS_TABLE_LIMIT:
                self.stdout.write("    ... 共 {} 行，仅展示前 {} 行".format(len(rows), CROSS_TABLE_LIMIT))
            self.stdout.write("    (耗时 %.1fs)" % (time.time() - started))
        else:
            self.stdout.write("")
            self.stdout.write("[C] 三维交叉：已跳过（--skip-latest）")

        # [D] 候选集（收窄后 sync 会扫的）
        candidate = running.filter(action__in=actions)
        candidate_count = candidate.count()
        self.stdout.write("")
        self.stdout.write("[D] 候选集 action__in={}（收窄后 sync 会扫的）: {}".format(actions, candidate_count))
        for row in candidate.values("action").annotate(c=Count("id")).order_by("-c"):
            self.stdout.write("    {:<24} {}".format(row["action"], row["c"]))

        # [E] 单独给出：候选集 且 风险已 CLOSED —— 本次治理目标
        self.stdout.write("")
        self.stdout.write("[E] 治理目标：候选集 且 risk.status = %s" % RiskStatus.CLOSED)
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT n.action, COUNT(*) FROM {node_table} n
                JOIN {risk_table} r ON r.risk_id = n.risk_id
                WHERE n.status = %s AND n.action IN ({placeholders}) AND r.status = %s
                GROUP BY n.action ORDER BY 2 DESC
                """,
                [TicketNodeStatus.RUNNING] + list(actions) + [RiskStatus.CLOSED],
            )
            detail = cursor.fetchall()
        if detail:
            for action, count in detail:
                self.stdout.write("    {:<24} {}".format(action, count))
        else:
            self.stdout.write("    （无）")
        self.stdout.write("    合计: %s" % sum(c for _, c in detail))

        # [F] 预估 sync 单次返回行数
        self.stdout.write("")
        self.stdout.write("[F] 预估 sync 单次返回行数:")
        self.stdout.write("    收窄前（历史慢查询口径）: %s" % total)
        self.stdout.write("    收窄后（当前代码口径）  : %s" % candidate_count)
        self.stdout.write("")

    def cross_table(self, node_table, risk_table):
        """按 action / 是否该风险最新节点 / risk.status 三维分组

        是否最新节点用 EXISTS 判断（走 risk_id 索引），避免全表自连接放大。
        """
        sql = f"""
            SELECT n.action,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM {node_table} m
                       WHERE m.risk_id = n.risk_id AND m.timestamp > n.timestamp
                   ) THEN 'no' ELSE 'yes' END AS is_latest,
                   r.status,
                   COUNT(*)
            FROM {node_table} n
            LEFT JOIN {risk_table} r ON r.risk_id = n.risk_id
            WHERE n.status = %s
            GROUP BY 1, 2, 3
            ORDER BY 4 DESC
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [TicketNodeStatus.RUNNING])
            return cursor.fetchall()

    # ------------------------------------------------------------------ 治理

    def clean(self, ctx, apply, batch_size, max_rounds):
        """仅清理「风险已关闭」的遗留 running 节点

        每轮只取「当前仍匹配」的一批并更新，更新后这些行不再匹配，
        因此不存在 LIMIT/OFFSET 分页导致的漏/重问题。
        """
        actions = ctx["actions"]
        placeholders = ctx["placeholders"]
        node_table = ctx["node_table"]
        risk_table = ctx["risk_table"]
        params = [TicketNodeStatus.RUNNING] + list(actions) + [RiskStatus.CLOSED]

        before = self.snapshot(ctx)

        count_sql = f"""
            SELECT COUNT(*) FROM {node_table} n
            JOIN {risk_table} r ON r.risk_id = n.risk_id
            WHERE n.status = %s AND n.action IN ({placeholders}) AND r.status = %s
        """
        select_sql = f"""
            SELECT n.id, n.risk_id, n.action FROM {node_table} n
            JOIN {risk_table} r ON r.risk_id = n.risk_id
            WHERE n.status = %s AND n.action IN ({placeholders}) AND r.status = %s
            LIMIT {int(batch_size)}
        """

        with connection.cursor() as cursor:
            cursor.execute(count_sql, params)
            to_clean = cursor.fetchone()[0]

        self.stdout.write("=" * 72)
        self.stdout.write("遗留治理：风险已关闭、但 %s 节点仍 running" % actions)
        self.stdout.write("=" * 72)
        self.stdout.write("待清理节点数: %s" % to_clean)

        changed = []
        if not apply:
            self.stdout.write("当前为只读模式，未写入任何数据；确认后加 --apply 执行。")
            self.stdout.write("")
            return changed

        if not to_clean:
            self.stdout.write("无待清理节点，跳过。")
            self.stdout.write("")
            return changed

        total_updated = 0
        rounds = 0
        while True:
            if max_rounds and rounds >= max_rounds:
                self.stdout.write("达到最大轮次 %s，停止（剩余节点下次命令继续）。" % max_rounds)
                break

            with connection.cursor() as cursor:
                cursor.execute(select_sql, params)
                batch = cursor.fetchall()

            if not batch:
                break

            node_ids = [row[0] for row in batch]
            updated = TicketNode.objects.filter(id__in=node_ids).update(status=TicketNodeStatus.FINISHED)
            changed.extend({"node_id": r[0], "risk_id": r[1], "action": r[2]} for r in batch)
            total_updated += updated
            rounds += 1
            logger.info(
                "[GovernRunningTicketNode] round=%s batch=%s updated=%s total=%s",
                rounds,
                len(node_ids),
                updated,
                total_updated,
            )
            self.stdout.write("  round {}: 本批 {} 条，累计 {} 条".format(rounds, updated, total_updated))

            if updated == 0:
                self.stdout.write("本批更新 0 条，提前结束以避免死循环，请人工核查。")
                break

        self.stdout.write("清理完成，累计更新 %s 条。" % total_updated)

        # 治理前后对比
        after = self.snapshot(ctx)
        self.stdout.write("")
        self.stdout.write("=" * 72)
        self.stdout.write("治理前后对比")
        self.stdout.write("=" * 72)
        self.stdout.write("    {:<28} {:>12} {:>12} {:>12}".format("指标", "治理前", "治理后", "变化"))
        self.stdout.write("    " + "-" * 68)
        for label, key in (
            ("running 总量", "total"),
            ("审批/套餐 running", "candidate"),
            ("预估 sync 单次返回行数", "candidate"),
        ):
            b, a = before[key], after[key]
            self.stdout.write("    {:<28} {:>12} {:>12} {:>12}".format(label, b, a, a - b))
        self.stdout.write("")

        return changed

    def snapshot(self, ctx):
        """取关键指标快照，用于治理前后对比"""
        running = TicketNode.objects.filter(status=TicketNodeStatus.RUNNING).order_by()
        return {
            "total": running.count(),
            "candidate": running.filter(action__in=ctx["actions"]).count(),
        }

    def dump_changed(self, changed, path):
        """落盘被修改记录，用于核对与回滚"""
        payload = {
            "finished_status": TicketNodeStatus.FINISHED,
            "rolled_back_to": TicketNodeStatus.RUNNING,
            "count": len(changed),
            "records": changed,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        self.stdout.write("已落盘 {} 条变更记录到 {}（回滚即把 status 改回 {}）。".format(len(changed), path, TicketNodeStatus.RUNNING))
