# -*- coding: utf-8 -*-
"""
审计并修复风险人员检索索引和风险等级快照。
"""

from typing import Dict, Iterable, Set, Tuple

from django.core.management.base import BaseCommand

from services.web.risk.models import Risk, RiskPersonIndex
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy

PersonPair = Tuple[str, str]


class Command(BaseCommand):
    help = "Audit and optionally repair Risk.risk_level snapshots and RiskPersonIndex rows."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=5000)
        parser.add_argument("--fix", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--skip-risk-level", action="store_true")
        parser.add_argument("--skip-person-index", action="store_true")
        parser.add_argument("--rebuild-risk-level", action="store_true")

    def handle(self, *args, **options):
        batch_size = max(int(options["batch_size"]), 1)
        fix = bool(options["fix"] and not options["dry_run"])
        skip_risk_level = options["skip_risk_level"]
        skip_person_index = options["skip_person_index"]
        rebuild_risk_level = options["rebuild_risk_level"]

        stats = self._empty_stats()
        queryset = Risk.objects.only(
            "risk_id",
            "strategy",
            "risk_level",
            "risk_level_order",
            "operator",
            "current_operator",
            "notice_users",
        ).order_by("risk_id")

        batch = []
        for risk in queryset.iterator(chunk_size=batch_size):
            batch.append(risk)
            if len(batch) >= batch_size:
                strategy_level_map = self._load_strategy_level_map(batch)
                self._process_batch(
                    batch, stats, fix, skip_risk_level, skip_person_index, rebuild_risk_level, strategy_level_map
                )
                self._write_progress(stats)
                batch = []
        if batch:
            strategy_level_map = self._load_strategy_level_map(batch)
            self._process_batch(
                batch, stats, fix, skip_risk_level, skip_person_index, rebuild_risk_level, strategy_level_map
            )
            self._write_progress(stats)

        self.stdout.write("# conclusion")
        for key, value in stats.items():
            self.stdout.write(f"{key}={value}")

    @staticmethod
    def _empty_stats() -> Dict[str, int]:
        return {
            "scanned": 0,
            "risk_level_mismatches": 0,
            "risk_level_missing_snapshots": 0,
            "risk_level_strategy_drifts": 0,
            "fixed_risk_levels": 0,
            "missing_strategy_risks": 0,
            "person_index_mismatch_risks": 0,
            "missing_person_pairs": 0,
            "extra_person_pairs": 0,
            "fixed_person_indexes": 0,
        }

    def _process_batch(
        self,
        risks: Iterable[Risk],
        stats: Dict[str, int],
        fix: bool,
        skip_risk_level: bool,
        skip_person_index: bool,
        rebuild_risk_level: bool,
        strategy_level_map: Dict[int, str],
    ) -> None:
        for risk in risks:
            stats["scanned"] += 1
            if not skip_risk_level:
                self._audit_risk_level(risk, stats, fix, rebuild_risk_level, strategy_level_map)
            if not skip_person_index:
                self._audit_person_index(risk, stats, fix)

    @staticmethod
    def _load_strategy_level_map(risks: Iterable[Risk]) -> Dict[int, str]:
        strategy_ids = {risk.strategy_id for risk in risks if risk.strategy_id}
        if not strategy_ids:
            return {}
        return dict(
            Strategy._base_manager.filter(strategy_id__in=strategy_ids).values_list("strategy_id", "risk_level")
        )

    def _audit_risk_level(
        self,
        risk: Risk,
        stats: Dict[str, int],
        fix: bool,
        rebuild_risk_level: bool,
        strategy_level_map: Dict[int, str],
    ) -> None:
        expected_level = None
        if risk.strategy_id and risk.strategy_id in strategy_level_map:
            expected_level = strategy_level_map[risk.strategy_id]
        elif risk.strategy_id:
            stats["missing_strategy_risks"] += 1
        expected_order = RiskLevel.order_value(expected_level)
        snapshot_order = RiskLevel.order_value(risk.risk_level)
        is_missing_snapshot = risk.risk_level is None
        is_snapshot_order_mismatch = risk.risk_level is not None and risk.risk_level_order != snapshot_order
        is_strategy_drift = risk.risk_level is not None and risk.risk_level != expected_level

        if not is_missing_snapshot and not is_snapshot_order_mismatch and not is_strategy_drift:
            return

        if is_missing_snapshot:
            stats["risk_level_mismatches"] += 1
            stats["risk_level_missing_snapshots"] += 1
        elif is_snapshot_order_mismatch:
            stats["risk_level_mismatches"] += 1
        if is_strategy_drift:
            stats["risk_level_strategy_drifts"] += 1

        if fix and rebuild_risk_level:
            self._save_risk_level(risk, expected_level, expected_order)
            stats["fixed_risk_levels"] += 1
        elif fix and is_missing_snapshot:
            self._save_risk_level(risk, expected_level, expected_order)
            stats["fixed_risk_levels"] += 1
        elif fix and is_snapshot_order_mismatch:
            self._save_risk_level(risk, risk.risk_level, snapshot_order)
            stats["fixed_risk_levels"] += 1

    @staticmethod
    def _save_risk_level(risk: Risk, risk_level: str, risk_level_order: int) -> None:
        if risk.risk_level != risk_level or risk.risk_level_order != risk_level_order:
            risk.risk_level = risk_level
            risk.risk_level_order = risk_level_order
            risk.save(update_fields=["risk_level", "risk_level_order"])

    def _audit_person_index(self, risk: Risk, stats: Dict[str, int], fix: bool) -> None:
        expected_pairs = self._expected_person_pairs(risk)
        active_pairs = set(RiskPersonIndex.objects.filter(risk_id=risk.risk_id).values_list("relation_type", "user"))
        missing_pairs = expected_pairs - active_pairs
        extra_pairs = active_pairs - expected_pairs
        if not missing_pairs and not extra_pairs:
            return

        stats["person_index_mismatch_risks"] += 1
        stats["missing_person_pairs"] += len(missing_pairs)
        stats["extra_person_pairs"] += len(extra_pairs)
        if fix:
            RiskPersonIndex.sync_risk(risk)
            stats["fixed_person_indexes"] += 1

    @staticmethod
    def _expected_person_pairs(risk: Risk) -> Set[PersonPair]:
        return {
            (relation_type, user)
            for relation_type, users in RiskPersonIndex.risk_relation_users(risk).items()
            for user in users
        }

    def _write_progress(self, stats: Dict[str, int]) -> None:
        self.stdout.write(
            "progress "
            f"scanned={stats['scanned']} "
            f"risk_level_mismatches={stats['risk_level_mismatches']} "
            f"person_index_mismatch_risks={stats['person_index_mismatch_risks']}"
        )
