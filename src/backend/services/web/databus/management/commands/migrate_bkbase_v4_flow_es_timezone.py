"""显式规划/应用单个已停用V4 Flow的ES UTC8到UTC0切日配置。

缺省只读，计划和只追加报告均以0600独占创建；每次发送前fsync完整备份。
不停止/启动任务，不删除索引，不自动重试结果未知的写入。
"""

import hashlib
import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from services.web.bkbase import flow_es_timezone
from services.web.bkbase.common import get_bkbase_context, get_bkbase_version
from services.web.bkbase.constants import BKBaseVersion

MAX_PLAN_BYTES = 1024 * 1024


def _write_event(handle, event):
    """先将计划/发送前旧值写入私有证据，刷盘失败即不发送。"""
    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def _new_file(path):
    """只新建私有文件，拒绝覆盖、软链接和已有报告。"""
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8")


class Command(BaseCommand):
    help = "预览或显式切换已停用V4 Flow的ES日模板timezone 8→0；不自动启停"

    def add_arguments(self, parser):
        parser.add_argument("--strategy-id", type=int, required=True)
        parser.add_argument("--audit-namespace", required=True)
        parser.add_argument("--flow-ref", required=True, help="正式Flow完整Ref的JSON，不使用旧数字flow_id")
        parser.add_argument("--plan", required=True, help="预览时新建计划；--apply时读取此前审核的同一计划")
        parser.add_argument("--report", required=True, help="每次新建的私有JSONL报告，不能覆盖")
        parser.add_argument("--apply", action="store_true", help="显式发送一次保持停止的PUT；缺省只读预览")

    def handle(self, *args, **options):
        if get_bkbase_version() != BKBaseVersion.V4:
            raise CommandError("仅允许在BKBase V4配置下切换ES切日时区")
        context = get_bkbase_context()
        failure_message = "计划、预览或本地证据处理失败，PUT尚未发送；保留计划和报告后核对"
        try:
            flow_ref = json.loads(options["flow_ref"])
            if options["apply"]:
                with Path(options["plan"]).open("rb") as source:
                    content = source.read(MAX_PLAN_BYTES + 1)
                if len(content) > MAX_PLAN_BYTES:
                    raise ValueError("计划超过1MiB限制")
                plan = json.loads(content)
                if not isinstance(plan, dict) or any(
                    plan.get(key) != expected
                    for key, expected in (
                        ("strategy_id", options["strategy_id"]),
                        ("audit_namespace", options["audit_namespace"]),
                        ("flow_ref", flow_ref),
                    )
                ):
                    raise ValueError("命令身份与已审核计划不一致")
            elif Path(options["plan"]).exists():
                raise ValueError("计划文件已存在，拒绝覆盖")
            with _new_file(options["report"]) as report:
                _write_event(
                    report,
                    {
                        "event": "begin",
                        "mode": "apply" if options["apply"] else "preview",
                        "strategy_id": options["strategy_id"],
                        "flow_ref": flow_ref,
                    },
                )
                try:
                    if options["apply"]:

                        def before_write():
                            nonlocal failure_message
                            _write_event(
                                report,
                                {
                                    "event": "before_send",
                                    "plan": plan,
                                    "plan_sha256": hashlib.sha256(content).hexdigest(),
                                },
                            )
                            # 备份已刷盘后即不能再按未发送提示，发送结果由apply_plan确认。
                            failure_message = "已进入PUT发送阶段，结果未确认；保留flow_write，只读核对配置/状态，勿按未发送重跑或清除凭据"

                        result = flow_es_timezone.apply_plan(context, plan, before_write=before_write)
                        if result == "accepted":
                            failure_message = "PUT已受理但报告落盘未确认；先只读核配置/状态，勿按未发送重跑"
                        _write_event(
                            report,
                            {
                                "event": result,
                                "strategy_id": options["strategy_id"],
                                "applied_state_verified": False,
                                "task_kept_stopped": True,
                            },
                        )
                    else:
                        plan = flow_es_timezone.preview(
                            context, options["strategy_id"], options["audit_namespace"], flow_ref
                        )
                        with _new_file(options["plan"]) as target:
                            _write_event(target, plan)
                        _write_event(report, {"event": "planned", "plan": plan})
                        result = "planned"
                except Exception as error:  # NOCC:broad-except(保留失败阶段，未知写不能盲目重试)
                    try:
                        _write_event(report, {"event": "error", "error_type": type(error).__name__})
                    except OSError:
                        # 报告仍不可写时保留原异常与已知发送阶段，不能退回“未发送”。
                        pass
                    raise CommandError(failure_message) from error
        except (OSError, ValueError) as error:
            raise CommandError(failure_message) from error
        self.stdout.write(f"{result}; only timezone 8→0; no automatic start or index deletion")
