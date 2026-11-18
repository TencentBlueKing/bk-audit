"""按明确清单分别导入普通/事件插件与采集项资源，默认只读预检。

每批最多20条；新建私有JSONL报告，在每次本地更新前fsync完整旧值。
远端仅GET，应用中断时沿报告核对已准备/已提交记录，不盲目重试或回滚。
"""

import hashlib
import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder

from services.web.bkbase import resource_migration
from services.web.bkbase.common import get_bkbase_context, get_bkbase_version
from services.web.bkbase.constants import BKBaseVersion
from services.web.bkbase.exceptions import BKBaseResourceMappingError

MAX_INPUT_BYTES = 1024 * 1024


def _write_event(handle, event):
    """数据库写入之前刷盘恢复记录，不覆盖已有报告。"""
    handle.write(json.dumps(event, ensure_ascii=False, cls=DjangoJSONEncoder) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


class Command(BaseCommand):
    help = "只读预检或显式导入plugin/event_plugin/collector的BKBase V4绑定（不改平台）"

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, help="包含owner、本地主键、旧身份及完整资源引用的JSON清单")
        parser.add_argument("--limit", type=int, default=resource_migration.MAX_BATCH_SIZE, help="本批最大条数，1–20，不截断")
        parser.add_argument("--report", required=True, help="新建私有JSONL报告路径，不能覆盖已有文件")
        parser.add_argument("--apply", action="store_true", help="显式写本地bkbase_v4_resources；默认只预检")

    def handle(self, *args, **options):
        if get_bkbase_version() != BKBaseVersion.V4:
            raise CommandError("仅允许在BKBase V4配置下导入")
        context = get_bkbase_context()
        try:
            with Path(options["input"]).open("rb") as source:
                content = source.read(MAX_INPUT_BYTES + 1)
            if len(content) > MAX_INPUT_BYTES:
                raise ValueError("输入清单超过1MiB限制")
            rows = resource_migration.validate_manifest(json.loads(content), context=context, limit=options["limit"])
        except (OSError, ValueError, BKBaseResourceMappingError) as error:
            raise CommandError(str(error)) from error
        try:
            fd = os.open(options["report"], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError as error:
            raise CommandError("无法新建私有报告；未修改本地绑定") from error
        mode = "apply" if options["apply"] else "dry-run"
        with os.fdopen(fd, "w", encoding="utf-8") as report:
            _write_event(
                report,
                {
                    "event": "manifest",
                    "schema_version": resource_migration.SCHEMA_VERSION,
                    "mode": mode,
                    "target_tenant": context["tenant"],
                    "count": len(rows),
                    "input_sha256": hashlib.sha256(content).hexdigest(),
                    "local_binding_only": True,
                },
            )
            plans, failures = [], 0
            for row in rows:
                try:
                    plan = resource_migration.preview_mapping(context, row)
                    plans.append((row, plan))
                    _write_event(report, {"event": "preview", "mapping": row, **plan})
                except Exception as error:  # NOCC:broad-except(每条失败必须写入私有报告)
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
                raise CommandError(f"预检失败{failures}条；整批未应用，详见报告")
            updated = unchanged = 0
            if options["apply"]:
                for row, plan in plans:
                    try:
                        result = resource_migration.apply_mapping(
                            context,
                            row,
                            plan,
                            before_save=lambda: _write_event(report, {"event": "before_apply", "mapping": row, **plan}),
                        )
                        updated += result == "updated"
                        unchanged += result == "unchanged"
                        _write_event(report, {"event": result, "owner": row["owner"], "owner_pk": row["owner_pk"]})
                    except Exception as error:  # NOCC:broad-except(保留已提交结果和失败位置，不盲目重试)
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
                        raise CommandError(f"应用失败；此前已更新{updated}条，请保留报告并核对恢复") from error
            _write_event(report, {"event": "complete", "mode": mode, "updated": updated, "unchanged": unchanged})
        self.stdout.write(f"{mode} scanned={len(rows)} updated={updated} unchanged={unchanged}")
