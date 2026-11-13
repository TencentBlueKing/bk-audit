"""有界补录已有 V4 Clean 的逻辑结果表 ID。"""
from django.core.management.base import BaseCommand, CommandError

from services.web.bkbase import clean
from services.web.bkbase.common import get_bkbase_context, get_bkbase_version
from services.web.bkbase.constants import BKBaseVersion
from services.web.databus.models import CollectorConfig, CollectorPlugin

OWNER_MODELS = {"plugin": CollectorPlugin, "collector": CollectorConfig}
MAX_BATCH_SIZE = 20


class Command(BaseCommand):
    help = "核对已有 BKBase V4 Clean 并补录逻辑结果表 ID"

    def add_arguments(self, parser):
        parser.add_argument("--owner", choices=OWNER_MODELS, required=True, help="补录插件或采集项")
        parser.add_argument("--after-pk", type=int, default=0, help="仅处理本地主键大于此值的记录")
        parser.add_argument("--limit", type=int, default=10, help=f"每批最多扫描 {MAX_BATCH_SIZE} 个本地主键")

    def handle(self, *args, **options):
        if get_bkbase_version() != BKBaseVersion.V4:
            raise CommandError("仅支持 BKBase V4")
        if options["after_pk"] < 0 or not 1 <= options["limit"] <= MAX_BATCH_SIZE:
            raise CommandError(f"after-pk 必须非负且 limit 必须在 1–{MAX_BATCH_SIZE} 之间")
        inspected, updated, skipped, failures, next_pk = clean.backfill_ready_logical_table_ids(
            get_bkbase_context(), OWNER_MODELS[options["owner"]], after_pk=options["after_pk"], limit=options["limit"]
        )
        for pk, error in failures:
            self.stderr.write(f"pk={pk} {error}")
        self.stdout.write(
            f"scanned={inspected} updated={updated} skipped={skipped} failed={len(failures)} next_after_pk={next_pk}"
        )
