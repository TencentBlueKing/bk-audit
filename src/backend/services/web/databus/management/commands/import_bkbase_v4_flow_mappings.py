"""按审计清单导入旧Flow到V4 Ref的权威映射，默认只预览。

每次最多20条，本地写前追加并fsync旧值证据；不触发平台写入或策略启停。
报告为仅追加JSON Lines，进程中断时仍可核对已准备和已提交的条目。
"""

import hashlib
import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from services.web.bkbase import flow_migration
from services.web.bkbase.common import get_bkbase_context, get_bkbase_version
from services.web.bkbase.constants import BKBaseVersion
from services.web.bkbase.exceptions import BKBaseResourceMappingError

MAX_INPUT_BYTES = 1024 * 1024


def _write_event(handle, event):
    """每次数据库变更前将恢复旧值刷盘，不覆盖已有证据。"""
    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


class Command(BaseCommand):
    help = "预览或显式导入审计旧Flow到BKBase V4的权威映射（不改平台）"

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, help='JSON flow_id→flow_name映射，如{"41":"migrated-flow"}；兼容旧版详细清单')
        parser.add_argument("--legacy-tenant", help="显式预期的旧租户或旧环境范围标识")
        parser.add_argument("--legacy-project-id", type=int, help="显式预期的旧BKBase项目ID")
        parser.add_argument("--limit", type=int, default=flow_migration.MAX_BATCH_SIZE, help="本批最大条数，不自动截断")
        parser.add_argument("--report", required=True, help="新建的私有JSONL报告路径，不能覆盖已有文件")
        parser.add_argument("--apply", action="store_true", help="显式写本地绑定；缺省dry-run")

    def handle(self, *args, **options):
        if get_bkbase_version() != BKBaseVersion.V4:
            raise CommandError("仅允许在BKBase V4配置下导入")
        context = get_bkbase_context()
        try:
            with Path(options["input"]).open("rb") as source:
                content = source.read(MAX_INPUT_BYTES + 1)
            if len(content) > MAX_INPUT_BYTES:
                raise ValueError("输入清单超过1MiB限制")
            payload = json.loads(content)
            rows = flow_migration.validate_manifest(
                payload,
                context=context,
                legacy_tenant=options["legacy_tenant"],
                legacy_project_id=options["legacy_project_id"],
                limit=options["limit"],
            )
            rows = flow_migration.resolve_mappings(context, rows)
        except (OSError, ValueError, BKBaseResourceMappingError) as error:
            raise CommandError(str(error)) from error
        try:
            fd = os.open(options["report"], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError as error:
            raise CommandError("无法新建报告文件；未修改本地绑定") from error
        mode = "apply" if options["apply"] else "dry-run"
        with os.fdopen(fd, "w", encoding="utf-8") as report:
            _write_event(
                report,
                {
                    "event": "manifest",
                    "schema_version": flow_migration.SCHEMA_VERSION,
                    "mode": mode,
                    "source": payload.get("source"),
                    "target_tenant": context["tenant"],
                    "input_sha256": hashlib.sha256(content).hexdigest(),
                    "count": len(rows),
                    "local_binding_only": True,
                },
            )
            plans, failures = [], 0
            for row in rows:
                try:
                    plan = flow_migration.preview_mapping(context, row)
                    plans.append((row, plan))
                    _write_event(report, {"event": "preview", "mapping": row, **plan})
                except Exception as error:  # NOCC:broad-except(每条失败必须写入本地报告)
                    failures += 1
                    _write_event(
                        report,
                        {
                            "event": "error",
                            "stage": "preview",
                            "mapping": row,
                            "error_type": type(error).__name__,
                            "error": str(error),
                        },
                    )
            if failures:
                raise CommandError(f"预览失败{failures}条；整批未应用，详见报告")
            updated = unchanged = 0
            if options["apply"]:
                for row, plan in plans:
                    try:
                        result = flow_migration.apply_mapping(
                            context,
                            row,
                            plan,
                            before_save=lambda: _write_event(report, {"event": "before_apply", "mapping": row, **plan}),
                        )
                        updated += result == "updated"
                        unchanged += result == "unchanged"
                        _write_event(report, {"event": result, "strategy_id": row["strategy_id"]})
                    except Exception as error:  # NOCC:broad-except(保留已提交结果与失败位置，绝不盲目重试)
                        _write_event(
                            report,
                            {
                                "event": "error",
                                "stage": "apply",
                                "mapping": row,
                                "error_type": type(error).__name__,
                                "error": str(error),
                            },
                        )
                        raise CommandError(f"应用失败；此前已更新{updated}条，保留报告后核对恢复") from error
            _write_event(report, {"event": "complete", "mode": mode, "updated": updated, "unchanged": unchanged})
            self.stdout.write(f"{mode} scanned={len(rows)} updated={updated} unchanged={unchanged}")
