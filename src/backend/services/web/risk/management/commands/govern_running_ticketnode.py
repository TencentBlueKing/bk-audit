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
#   - 只写 TicketNode.status，禁止改动业务库其它表。
#
# 用法：
#   python manage.py govern_running_ticketnode                       # 只读统计
#   python manage.py govern_running_ticketnode --apply               # 治理并输出前后对比

from blueapps.utils.logger import logger
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import OperationalError, connection
from django.db.models import Count

from services.web.risk.constants import RiskStatus, TicketNodeStatus
from services.web.risk.handlers.ticket import AutoProcess, ForApprove
from services.web.risk.models import Risk, TicketNode

# 需要跟外部系统（ITSM / SOPS）同步状态的节点；其余节点按设计长期保持 running
DEFAULT_GOVERN_ACTIONS = [ForApprove.__name__, AutoProcess.__name__]


class Command(BaseCommand):
    help = "TicketNode RUNNING 存量统计与遗留治理（一次性数据治理，默认只读）"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="执行清理；默认只统计，不写库")
        parser.add_argument("--batch-size", type=int, default=500, help="每批更新条数，默认 500")
        parser.add_argument("--max-rounds", type=int, default=0, help="最大清理轮次，0 表示不限")
        parser.add_argument("--actions", type=str, default="", help="治理的 action，逗号分隔；默认审批+套餐")
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
            metrics = self.stats(ctx)
            self.capacity_stats(ctx, metrics)

        self.clean(ctx, options["apply"], options["batch_size"], options["max_rounds"])

    # ------------------------------------------------------------------ 统计

    def stats(self, ctx):
        actions = ctx["actions"]
        placeholders = ctx["placeholders"]
        node_table = ctx["node_table"]
        risk_table = ctx["risk_table"]

        running = TicketNode.objects.filter(status=TicketNodeStatus.RUNNING).order_by()

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write("TicketNode 表 running 记录统计（只读）")
        self.stdout.write("=" * 80)
        self.stdout.write("说明：")
        self.stdout.write("  - TicketNode：单据节点/执行记录表；running 指 TicketNode.status=running。")
        self.stdout.write("  - Risk：风险单表。")
        self.stdout.write("  - sync_auto_result：周期任务 services.web.risk.tasks.sync_auto_result，")
        self.stdout.write("    按 TicketNode 候选派发 sync_one_auto_result。")
        self.stdout.write("  - process_risk_ticket：周期任务 services.web.risk.tasks.process_risk_ticket，")
        self.stdout.write("    按 Risk 候选派发 process_one_risk。")

        # [A] running 总量
        total = running.count()
        self.stdout.write("")
        self.stdout.write("[A] TicketNode(status=running) 记录总数: %s" % total)

        # [B] 按 action 分组
        self.stdout.write("")
        self.stdout.write("[B] TicketNode 按 action 分组（每行是节点记录，不是风险单）:")
        for row in running.values("action").annotate(c=Count("id")).order_by("-c"):
            self.stdout.write("    {:<24} {}".format(row["action"], row["c"]))

        # [D] 候选集（收窄后 sync 会扫的）
        candidate = running.filter(action__in=actions)
        candidate_count = candidate.count()
        sync_rows = list(candidate.values("action").annotate(c=Count("id")).order_by("-c"))
        sync_by_action = {row["action"]: row["c"] for row in sync_rows}
        self.stdout.write("")
        self.stdout.write(
            "[D] sync_auto_result 候选：TicketNode(status=running, action in {}) 记录数: {}".format(actions, candidate_count)
        )
        for row in sync_rows:
            self.stdout.write("    {:<24} {}".format(row["action"], row["c"]))

        # [E] 单独给出：候选集 且 风险已 CLOSED —— 本次治理目标
        self.stdout.write("")
        self.stdout.write(
            "[E] govern_running_ticketnode 治理目标：上述 sync 候选中，" "对应 Risk.status=%s 的 TicketNode 记录" % RiskStatus.CLOSED
        )
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
        self.stdout.write("[F] sync_auto_result 单次候选行数对比:")
        self.stdout.write("    优化前：TicketNode(status=running) 全量（历史慢查询口径）: %s" % total)
        self.stdout.write("    优化后：TicketNode(status=running, action in ...) 收窄: %s" % candidate_count)
        self.stdout.write("")
        return {
            "running_total": total,
            "sync_candidates": candidate_count,
            "sync_by_action": sync_by_action,
        }

    # ------------------------------------------------------------------ 容量统计

    @staticmethod
    def _parse_period_minutes(value):
        """解析周期配置：支持 */N；固定分钟按 cron 语义视为每小时一次。"""
        if value is None:
            return None
        raw = str(value).strip()
        if raw.startswith("*/"):
            try:
                return max(1, int(raw[2:]))
            except ValueError:
                return None
        if raw.isdigit():
            return 60
        return None

    @staticmethod
    def _parse_rate_per_second(value):
        """解析限流配置：N/s、N/m、N/h，统一成每秒。"""
        if value is None:
            return None
        raw = str(value).strip().lower()
        if "/" not in raw:
            return None
        number, unit = raw.split("/", 1)
        try:
            rate = float(number)
        except ValueError:
            return None
        unit = unit.strip()
        if unit in ("s", "sec", "second"):
            return rate
        if unit in ("m", "min", "minute"):
            return rate / 60.0
        if unit in ("h", "hour"):
            return rate / 3600.0
        return None

    @staticmethod
    def _fmt_seconds(value):
        if value is None:
            return "无法计算"
        return "{:.0f}s（{:.1f}min）".format(value, value / 60)

    def capacity_stats(self, ctx, metrics):
        """[G][H][I] 候选集、每轮任务数、按环境变量的理论容量。"""
        process_statuses = [RiskStatus.NEW, RiskStatus.FOR_APPROVE, RiskStatus.AUTO_PROCESS]
        process_qs = Risk.objects.filter(status__in=process_statuses, strategy__is_formal=True)
        process_by_status = {
            row["status"]: row["c"] for row in process_qs.values("status").annotate(c=Count("risk_id"))
        }
        process_total = sum(process_by_status.values())

        sync_by_action = metrics.get("sync_by_action") or {}
        sync_total = metrics.get("sync_candidates") or 0
        total_messages = sync_total + process_total

        sync_period = self._parse_period_minutes(getattr(settings, "SYNC_AUTO_RESULT_PERIODIC_TASK_MINUTE", None))
        process_period = self._parse_period_minutes(getattr(settings, "PROCESS_ONE_RISK_PERIODIC_TASK_MINUTE", None))

        self.stdout.write("")
        self.stdout.write(
            "[G] process_risk_ticket 候选：Risk(status in NEW/FOR_APPROVE/AUTO_PROCESS, "
            "strategy.is_formal=True) 风险单数: %s" % process_total
        )
        for status in process_statuses:
            self.stdout.write("    {:<24} {}".format(status, process_by_status.get(status, 0)))

        self.stdout.write("")
        self.stdout.write("[H] 两个周期任务每轮投递的消息数:")
        self.stdout.write("    sync_auto_result：按 TicketNode 候选，每轮 %s 条" % sync_total)
        self.stdout.write("    process_risk_ticket：按 Risk 候选，每轮 %s 条" % process_total)
        self.stdout.write("    合计每轮消息：%s 条" % total_messages)

        sops_read_rate = self._parse_rate_per_second(getattr(settings, "SOPS_API_RATE_LIMIT", None))
        itsm_rate = self._parse_rate_per_second(getattr(settings, "ITSM_API_RATE_LIMIT", None))

        sync_approve = sync_by_action.get("ForApprove", 0)
        sync_auto = sync_by_action.get("AutoProcess", 0)
        process_approve = process_by_status.get(RiskStatus.FOR_APPROVE, 0)
        process_auto = process_by_status.get(RiskStatus.AUTO_PROCESS, 0)

        itsm_demand = sync_approve + process_approve
        sops_demand = sync_auto + process_auto
        period_seconds = (sync_period or process_period or 10) * 60
        sops_write_upper = 2 * max(sync_auto, process_auto)
        sops_write_rate = self._parse_rate_per_second(getattr(settings, "SOPS_OPERATE_API_RATE_LIMIT", None))
        sops_write_drain = sops_write_upper / sops_write_rate if sops_write_rate else None

        self.stdout.write("")
        self.stdout.write("[I] 理论容量/等待（基于当前候选 + 环境变量，不是实测耗时）")
        self.stdout.write("    计算口径：")
        self.stdout.write("      ITSM 读需求 = sync TicketNode(ForApprove) + process Risk(FOR_APPROVE)")
        self.stdout.write("      SOPS 读需求 = sync TicketNode(AutoProcess) + process Risk(AUTO_PROCESS)")
        self.stdout.write("      排空时间 = 需求 / 对应限流速率")
        self.stdout.write(
            "    SOPS 读（get_template_info/get_task_status/get_node_data 等）: "
            "需求 %s 次/轮，速率 %s，排空 %s"
            % (
                sops_demand,
                getattr(settings, "SOPS_API_RATE_LIMIT", "?"),
                self._fmt_seconds(sops_demand / sops_read_rate if sops_read_rate else None),
            )
        )
        self.stdout.write(
            "    SOPS 写上限（假设所有 AutoProcess 都需要 create+start，取 max）: "
            "需求 %s 次/轮（2 × max(%s, %s)），速率 %s，排空 %s / 周期 %ss -> %s"
            % (
                sops_write_upper,
                sync_auto,
                process_auto,
                getattr(settings, "SOPS_OPERATE_API_RATE_LIMIT", "?"),
                self._fmt_seconds(sops_write_drain),
                period_seconds,
                "超出，会积压"
                if sops_write_drain is not None and sops_write_drain > period_seconds
                else ("余量 %.0fs" % (period_seconds - sops_write_drain) if sops_write_drain is not None else "无法计算"),
            )
        )
        self.stdout.write("      说明：已有 task_id 的 AutoProcess 实际只读不写，所以这是上限。")
        self.stdout.write(
            "    ITSM 读（get_ticket_status/ticket_detail/workflows 等）: "
            "需求 %s 次/轮，速率 %s，排空 %s"
            % (
                itsm_demand,
                getattr(settings, "ITSM_API_RATE_LIMIT", "?"),
                self._fmt_seconds(itsm_demand / itsm_rate if itsm_rate else None),
            )
        )

        if itsm_rate:
            itsm_drain = itsm_demand / itsm_rate
            self.stdout.write(
                "    两路合计 ITSM 读排空: %s / 周期 %ss -> %s"
                % (
                    self._fmt_seconds(itsm_drain),
                    period_seconds,
                    "超出，会积压" if itsm_drain > period_seconds else "余量 %.0fs" % (period_seconds - itsm_drain),
                )
            )
        if sops_read_rate:
            sops_drain = sops_demand / sops_read_rate
            self.stdout.write(
                "    两路合计 SOPS 读排空: %s / 周期 %ss -> %s"
                % (
                    self._fmt_seconds(sops_drain),
                    period_seconds,
                    "超出，会积压" if sops_drain > period_seconds else "余量 %.0fs" % (period_seconds - sops_drain),
                )
            )

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
            SELECT n.id, n.action FROM {node_table} n
            JOIN {risk_table} r ON r.risk_id = n.risk_id
            WHERE n.status = %s AND n.action IN ({placeholders}) AND r.status = %s
            LIMIT {int(batch_size)}
        """
        # 只锁 TicketNode 行，不 JOIN Risk；避免与 process_one_risk（先锁 Risk 再更新
        # TicketNode）形成相反的加锁顺序导致死锁。Risk.status=closed 已在 SELECT 时筛选。
        update_sql = f"""
            UPDATE {node_table}
            SET status = %s
            WHERE id = %s AND status = %s AND action = %s
        """

        with connection.cursor() as cursor:
            cursor.execute(count_sql, params)
            to_clean = cursor.fetchone()[0]

        self.stdout.write("=" * 72)
        self.stdout.write("[治理] TicketNode：对应 Risk.status=closed，但 action in %s 的节点仍 running" % actions)
        self.stdout.write("=" * 72)
        self.stdout.write("待清理 TicketNode 记录数: %s" % to_clean)

        if not apply:
            self.stdout.write("当前为只读模式，未写入任何数据；确认后加 --apply 执行。")
            self.stdout.write("")
            return

        if not to_clean:
            self.stdout.write("无待清理节点，跳过。")
            self.stdout.write("")
            return

        total_updated = 0
        rounds = 0
        no_progress_rounds = 0
        while True:
            if max_rounds and rounds >= max_rounds:
                self.stdout.write("达到最大轮次 %s，停止（剩余节点下次命令继续）。" % max_rounds)
                break

            with connection.cursor() as cursor:
                cursor.execute(select_sql, params)
                batch = cursor.fetchall()

            if not batch:
                break

            # 逐行更新：只锁 TicketNode 行，避免跨表死锁；Risk.status=closed 已在 SELECT 时筛选。
            # 锁冲突（1205/1213）跳过当前行，留给下一轮或下次命令，不中断整批。
            updated = 0
            skipped = 0
            with connection.cursor() as cursor:
                for node_id, action in batch:
                    try:
                        cursor.execute(
                            update_sql,
                            [
                                TicketNodeStatus.FINISHED,
                                node_id,
                                TicketNodeStatus.RUNNING,
                                action,
                            ],
                        )
                    except OperationalError as err:
                        errno = err.args[0] if err.args else None
                        if errno in (1205, 1213):
                            skipped += 1
                            logger.warning(
                                "[GovernRunningTicketNode] lock conflict, skip node_id=%s err=%s",
                                node_id,
                                err,
                            )
                            continue
                        raise
                    if cursor.rowcount:
                        updated += cursor.rowcount

            total_updated += updated
            rounds += 1
            logger.info(
                "[GovernRunningTicketNode] round=%s batch=%s updated=%s skipped=%s total=%s",
                rounds,
                len(batch),
                updated,
                skipped,
                total_updated,
            )
            self.stdout.write(
                "  round {}: 本批 {} 条，实际更新 {} 条，锁冲突跳过 {} 条，累计 {} 条".format(
                    rounds, len(batch), updated, skipped, total_updated
                )
            )

            if updated == 0:
                no_progress_rounds += 1
                if no_progress_rounds >= 3:
                    self.stdout.write("连续 3 轮无实际更新，停止以避免死循环，请人工核查。")
                    break
            else:
                no_progress_rounds = 0

        self.stdout.write("清理完成，累计更新 TicketNode 记录 %s 条。" % total_updated)

        # 治理前后对比
        after = self.snapshot(ctx)
        self.stdout.write("")
        self.stdout.write("=" * 72)
        self.stdout.write("治理前后对比")
        self.stdout.write("=" * 72)
        self.stdout.write("    {:<28} {:>12} {:>12} {:>12}".format("指标", "治理前", "治理后", "变化"))
        self.stdout.write("    " + "-" * 68)
        for label, key in (
            ("TicketNode running 总量", "total"),
            ("ForApprove/AutoProcess running 节点", "candidate"),
            ("sync_auto_result 单次候选行数", "candidate"),
        ):
            b, a = before[key], after[key]
            self.stdout.write("    {:<28} {:>12} {:>12} {:>12}".format(label, b, a, a - b))
        self.stdout.write("")

    def snapshot(self, ctx):
        """取关键指标快照，用于治理前后对比"""
        running = TicketNode.objects.filter(status=TicketNodeStatus.RUNNING).order_by()
        return {
            "total": running.count(),
            "candidate": running.filter(action__in=ctx["actions"]).count(),
        }
