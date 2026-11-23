import json
import os
from argparse import ArgumentTypeError
from pathlib import Path
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.permission.iam_v4_model.client import ModelAPIError, ModelClient
from apps.permission.iam_v4_model.model import load_model
from apps.permission.iam_v4_model.reconcile import build_plan

DEFAULT_MODEL = Path(__file__).resolve().parents[4] / "support-files/iam_v4/model.json"
CALLBACK_PATH = "/api/v1/iam/resources/"


def _csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _csv(value: str) -> list[str]:
    values = _csv_values(value)
    if not values:
        raise ArgumentTypeError("expected a non-empty comma-separated list")
    return values


def _model_tenant(explicit: str | None) -> str | None:
    # 全租户应用共用一份模型；部署实例的租户不是模型注册的租户。
    if settings.BKPAAS_MULTI_TENANT_MODE:
        if explicit and explicit != "system":
            raise ValueError("multi-tenant IAM model management requires tenant=system")
        return "system"
    return explicit


class Command(BaseCommand):
    help = "Preview or explicitly reconcile the audit IAM V4 permission model."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
        parser.add_argument("--callback-url", help="Override the callback derived from BKAPP_BK_IAM_RESOURCE_API_HOST.")
        parser.add_argument("--clients", type=_csv, help="Replace the IAM system client list (comma-separated).")
        parser.add_argument("--managers", type=_csv, help="Set the IAM system manager list on first registration only.")
        parser.add_argument("--tenant-id", help="Set the tenant header if required by a single-tenant gateway.")
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--dry-run", action="store_true", help="Only read IAM and print the proposed changes (default)."
        )
        group.add_argument("--apply", action="store_true", help="Apply the current model plan, including deletions.")
        parser.add_argument("--expect-plan", help="Optionally reject changes if the plan digest differs.")
        parser.add_argument(
            "--snapshot-dir",
            type=Path,
            help="Existing private directory; defaults to ~/.local/state/bk-audit/iam-v4-snapshots.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        system_id = settings.BK_IAM_SYSTEM_ID
        try:
            tenant_id = _model_tenant(options["tenant_id"])
            callback_url = options["callback_url"]
            if callback_url is None:
                host = settings.BK_IAM_RESOURCE_API_HOST.rstrip("/")
                if not host:
                    raise ValueError("configure BKAPP_BK_IAM_RESOURCE_API_HOST or provide --callback-url")
                callback_url = host + CALLBACK_PATH
            client = ModelClient(settings.BK_IAM_V4_API_URL, settings.APP_CODE, settings.SECRET_KEY, tenant_id)
            current = client.fetch(system_id)
            current_system = current.system if current is not None else {}
            # 未显式指定客户端时保留线上名单；模型渲染时会补入当前应用。
            clients = (
                options["clients"]
                or _csv_values(os.getenv("BKAPP_IAM_V4_MODEL_CLIENTS", ""))
                or current_system.get("clients", [])
            )
            # 管理员配置只用于首次注册，更新模型时不覆盖线上名单。
            if current is None:
                managers = options["managers"] or _csv_values(os.getenv("BKAPP_IAM_V4_MODEL_MANAGERS", ""))
            else:
                managers = current_system["managers"]
            target = load_model(
                options["model"],
                system_id=system_id,
                app_code=settings.APP_CODE,
                system_name=settings.BK_IAM_SYSTEM_NAME,
                callback_url=callback_url,
                clients=clients,
                managers=managers,
            )
            plan = build_plan(target, current, gateway_url=client.gateway_url, tenant_id=tenant_id)
        except (OSError, ValueError, ModelAPIError) as exc:
            raise CommandError(str(exc)) from None

        self.stdout.write(
            f"{'apply' if apply else 'dry-run'} gateway={client.gateway_url} system={system_id} "
            f"tenant={tenant_id or '(gateway default)'} changes={len(plan.steps)} blocked={len(plan.blocked)}"
        )
        for change in plan.steps:
            line = change.label
            if change.method == "PUT":
                line += f" fields={','.join(sorted(change.body))}"
            self.stdout.write(line)
            if change.kind == "system" and change.method == "PUT" and "clients" in change.body:
                before = json.dumps(current_system["clients"], ensure_ascii=False)
                after = json.dumps(change.body["clients"], ensure_ascii=False)
                self.stdout.write(f"  clients: {before} -> {after}")
        for reason in plan.blocked:
            self.stdout.write(f"blocked: {reason}")
        self.stdout.write(f"plan_digest={plan.digest}")
        if not apply:
            return
        if options["expect_plan"] is not None and options["expect_plan"] != plan.digest:
            raise CommandError("IAM target or model changed; review a new preview before applying")
        if plan.blocked:
            raise CommandError("IAM model change blocked; resolve the reported authorization constraints first")
        if not plan.steps:
            return

        try:
            snapshot_dir = options["snapshot_dir"]
            if snapshot_dir is None:
                snapshot_dir = Path.home() / ".local/state/bk-audit/iam-v4-snapshots"
                snapshot_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            # 写入前保存变更前和目标模型；快照文件仅执行用户可读写，且不会覆盖上次快照。
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=snapshot_dir, prefix="iam-v4-", suffix=".json", delete=False
            ) as snapshot:
                json.dump(
                    {
                        "gateway": client.gateway_url,
                        "tenant": tenant_id,
                        "system_id": system_id,
                        "plan_digest": plan.digest,
                        "before": current.document() if current is not None else None,
                        "target": target.document(),
                    },
                    snapshot,
                    ensure_ascii=False,
                    indent=2,
                )
        except (OSError, RuntimeError):  # 无法确定用户主目录时，Path.home() 抛出 RuntimeError。
            raise CommandError("cannot save the pre-apply model snapshot; no IAM writes attempted") from None
        self.stdout.write(f"snapshot={snapshot.name}")

        for index, step in enumerate(plan.steps):
            try:
                client.mutate(step.method, step.path, json_body=step.body, params=step.params)
            except ModelAPIError as exc:
                remaining = len(plan.steps) - index - 1
                raise CommandError(
                    f"IAM stopped at {step.label}: {exc}; completed={index}, remaining={remaining}. "
                    "Re-read IAM and preview before retrying; partial changes may exist."
                ) from None
            self.stdout.write(f"completed: {step.label}")
        # IAM 接口不共用事务；全部请求成功后，还要重新读取模型确认与目标一致。
        try:
            actual = client.fetch(system_id)
        except ModelAPIError as exc:
            raise CommandError(f"IAM readback failed after applying the plan: {exc}") from None
        if actual != target:
            raise CommandError("IAM readback did not match the target; review a fresh preview")
        self.stdout.write(f"verified: system={system_id} changes={len(plan.steps)}")
