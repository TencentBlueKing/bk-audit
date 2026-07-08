# -*- coding: utf-8 -*-
"""风险导出服务。

同步导出和异步邮件导出共用本服务，负责风险数据组装、事件补充和 XLSX 文件生成。
"""

import base64
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Dict, List

from bk_resource import resource
from django.conf import settings
from rest_framework.settings import api_settings

from apps.notice.models import NoticeContent, NoticeContentConfig
from apps.notice.senders.mail import MailSender
from core.exporter.constants import ExportField
from core.utils.data import data2string, data_chunks
from core.utils.time import ceil_to_second, mstimestamp_to_date_string
from services.web.risk.constants import (
    EVENT_EXPORT_FIELD_PREFIX,
    RISK_EXPORT_FILE_NAME_TMP,
    RiskDisplayStatus,
    RiskExportField,
    RiskViewType,
)
from services.web.risk.handlers.risk_export import MultiSheetRiskExporterXlsx
from services.web.risk.models import Risk
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy

logger = logging.getLogger(__name__)


@dataclass
class RiskExportFile:
    """风险导出生成的文件对象及邮件/响应所需元信息。"""

    file: BinaryIO
    filename: str
    total: int
    view_label: str


class RiskExportService:
    """风险导出领域服务，负责将上层已授权风险单及最近事件转换为多 Sheet XLSX。"""

    def __init__(
        self,
        username: str,
        risk_ids: List[str],
        risk_view_type: str = "",
    ) -> None:
        self.username = username
        self.risk_ids = risk_ids
        self.risk_view_type = risk_view_type

    @classmethod
    def build_filename(cls, risk_view_type: str) -> str:
        """按风险视图类型和当前时间生成导出文件名。"""

        return RISK_EXPORT_FILE_NAME_TMP.format(
            risk_view_type=str(RiskViewType.get_label(risk_view_type)),
            datetime=datetime.now().strftime("%Y%m%d_%H%M%S"),
        )

    def build_export_file(self) -> RiskExportFile:
        """生成风险导出 XLSX 文件。

        XLSX 写入使用临时文件和 xlsxwriter constant_memory，但风险与事件行当前会先组装到内存中。
        """

        logger.info(
            "[RiskExportService] build export file start username=%s total=%s risk_view_type=%s",
            self.username,
            len(self.risk_ids),
            self.risk_view_type,
        )
        risks = self._load_risks()
        logger.info("[RiskExportService] risks loaded username=%s loaded=%s", self.username, len(risks))
        strategy_export_fields = self._build_strategy_export_fields(risks)
        formatted_risks_by_strategy = self._build_rows(risks)
        exporter = MultiSheetRiskExporterXlsx()
        exporter.write(sheets_data=formatted_risks_by_strategy, sheets_headers=strategy_export_fields)
        export_file = RiskExportFile(
            file=exporter.save(),
            filename=self.build_filename(self.risk_view_type),
            total=len(self.risk_ids),
            view_label=str(RiskViewType.get_label(self.risk_view_type)),
        )
        logger.info(
            "[RiskExportService] build export file finished username=%s total=%s sheets=%s filename=%s",
            self.username,
            export_file.total,
            len(formatted_risks_by_strategy),
            export_file.filename,
        )
        return export_file

    def _load_risks(self) -> List[Risk]:
        """按请求顺序加载风险单，权限校验由入口解析阶段负责。"""

        risks = Risk.prefetch_strategy_tags(Risk.annotated_queryset()).filter(risk_id__in=self.risk_ids)
        risk_map = {risk.risk_id: risk for risk in risks}
        return [risk_map[risk_id] for risk_id in self.risk_ids if risk_id in risk_map]

    def _build_strategy_export_fields(self, risks: List[Risk]) -> Dict[str, List[ExportField]]:
        """按策略构造 Sheet 表头，事件字段跟随策略配置。"""

        strategies = list(
            Strategy.objects.filter(strategy_id__in={risk.strategy_id for risk in risks}).order_by("strategy_id")
        )
        strategy_export_fields: Dict[str, List[ExportField]] = defaultdict(list)
        for strategy in strategies:
            risk_basic_fields = RiskExportField.export_fields()
            event_fields = [
                ExportField(
                    raw_name=f"{EVENT_EXPORT_FIELD_PREFIX}{field['field_name']}",
                    display_name=field["display_name"] or field["field_name"],
                )
                for field in strategy.event_data_field_configs
            ]
            strategy_export_fields[strategy.build_sheet_name()] = risk_basic_fields + event_fields
        return strategy_export_fields

    def _build_rows(self, risks: List[Risk]) -> Dict[str, List[dict]]:
        """组装导出行数据；一个风险最多展开最近 N 条事件。"""

        logger.info("[RiskExportService] build rows start username=%s total=%s", self.username, len(risks))
        bulk_resp = self._fetch_events(risks)
        formatted_risks_by_strategy = defaultdict(list)
        for risk, resp in zip(risks, bulk_resp):
            risk_basic_data = self._build_risk_basic_data(risk)
            events = resp["results"]
            if not events:
                formatted_risks_by_strategy[risk.strategy.build_sheet_name()].append(risk_basic_data)
                continue
            for event in events:
                event_data = {
                    field["field_name"]: event.get("event_data", {}).get(field["field_name"], "")
                    for field in risk.strategy.event_data_field_configs
                }
                formatted_risk = {
                    **risk_basic_data,
                    **{f"{EVENT_EXPORT_FIELD_PREFIX}{key}": value for key, value in event_data.items()},
                }
                formatted_risks_by_strategy[risk.strategy.build_sheet_name()].append(formatted_risk)
        logger.info(
            "[RiskExportService] build rows finished username=%s total=%s sheets=%s rows=%s",
            self.username,
            len(risks),
            len(formatted_risks_by_strategy),
            sum(len(rows) for rows in formatted_risks_by_strategy.values()),
        )
        return formatted_risks_by_strategy

    def _fetch_events(self, risks: List[Risk]) -> list:
        """复用现有 bulk_request 拉取每个风险最近的事件数据。"""

        total = len(risks)
        batch_size = max(settings.RISK_EXPORT_EVENT_FETCH_BATCH_SIZE, 1)
        batch_count = (total + batch_size - 1) // batch_size
        logger.info(
            "[RiskExportService] fetch events start username=%s total=%s event_limit=%s batch_size=%s",
            self.username,
            total,
            settings.RISK_EXPORT_EVENT_LIMIT_PER_RISK,
            batch_size,
        )
        bulk_resp = []
        for batch_index, risk_batch in enumerate(data_chunks(risks, batch_size), start=1):
            start_position = len(bulk_resp) + 1
            end_position = start_position + len(risk_batch) - 1
            logger.info(
                "[RiskExportService] fetch events batch start username=%s batch=%s/%s range=%s-%s total=%s",
                self.username,
                batch_index,
                batch_count,
                start_position,
                end_position,
                total,
            )
            bulk_events_params = [self._build_event_query_params(risk) for risk in risk_batch]
            batch_resp = resource.risk.list_event.bulk_request(bulk_events_params)
            bulk_resp.extend(batch_resp)
            logger.info(
                "[RiskExportService] fetch events batch finished "
                "username=%s batch=%s/%s current=%s total=%s fetched=%s",
                self.username,
                batch_index,
                batch_count,
                len(bulk_resp),
                total,
                len(batch_resp),
            )
        logger.info("[RiskExportService] fetch events finished username=%s total=%s", self.username, len(bulk_resp))
        return bulk_resp

    def _build_event_query_params(self, risk: Risk) -> dict:
        """构造单个风险查询最近事件的请求参数。"""

        start_time = mstimestamp_to_date_string(int(risk.event_time.timestamp() * 1000))
        event_end_time = ceil_to_second(risk.event_end_time) or datetime.now()
        end_time = mstimestamp_to_date_string(int(event_end_time.timestamp() * 1000))
        return {
            "risk_id": risk.risk_id,
            "start_time": start_time,
            "end_time": end_time,
            "page": 1,
            "page_size": settings.RISK_EXPORT_EVENT_LIMIT_PER_RISK,
        }

    def _build_risk_basic_data(self, risk: Risk) -> dict:
        """构造单条风险的基础字段。"""

        return {
            RiskExportField.RISK_ID: risk.risk_id,
            RiskExportField.RISK_TITLE: risk.title,
            RiskExportField.EVENT_CONTENT: risk.event_content,
            RiskExportField.RISK_TAGS: data2string([tag_rel.tag.tag_name for tag_rel in risk.strategy.prefetched_tags]),
            RiskExportField.EVENT_TYPE: data2string(risk.event_type),
            RiskExportField.RISK_LEVEL: str(RiskLevel.get_label(risk.risk_level)),
            RiskExportField.STRATEGY_NAME: risk.strategy.strategy_name,
            RiskExportField.STRATEGY_ID: risk.strategy.strategy_id,
            RiskExportField.RAW_EVENT_ID: risk.raw_event_id,
            RiskExportField.EVENT_END_TIME: (
                risk.event_end_time.strftime(api_settings.DATETIME_FORMAT) if risk.event_end_time else ""
            ),
            RiskExportField.EVENT_TIME: risk.event_time.strftime(api_settings.DATETIME_FORMAT),
            RiskExportField.RISK_HAZARD: risk.strategy.risk_hazard,
            RiskExportField.RISK_GUIDANCE: risk.strategy.risk_guidance,
            RiskExportField.STATUS: str(RiskDisplayStatus.get_label(risk.display_status)),
            RiskExportField.RULE_ID: risk.rule_id,
            RiskExportField.OPERATOR: data2string(risk.operator),
            RiskExportField.CURRENT_OPERATOR: data2string(risk.current_operator),
            RiskExportField.NOTICE_USERS: data2string(risk.notice_users),
        }

    def send_mail(self, export_file: RiskExportFile, requested_at: str) -> dict:
        """将导出文件作为邮件附件发送给当前用户。

        邮件 API 要求附件内容为 base64，因此这里会一次性读取导出文件并产生短时内存峰值。
        """

        logger.info(
            "[RiskExportService] send mail start username=%s total=%s filename=%s",
            self.username,
            export_file.total,
            export_file.filename,
        )
        export_file.file.seek(0)
        attachment_content = base64.b64encode(export_file.file.read()).decode("utf-8")
        attachment = {
            "filename": export_file.filename,
            "content": attachment_content,
            "type": "xlsx",
            "disposition": "attachment",
        }
        logger.info(
            "[RiskExportService] mail attachment ready username=%s filename=%s encoded_size=%s",
            self.username,
            export_file.filename,
            len(attachment_content),
        )
        content = NoticeContent(
            NoticeContentConfig(
                key="body",
                name="",
                value=(
                    f"您好 {self.username}：\n"
                    f"您于 {requested_at} 在「{export_file.view_label}」中发起的批量导出任务已完成。"
                    f"本次共导出风险单 {export_file.total} 条，详细数据请见附件\n"
                    "此邮件为系统自动发送，请勿直接回复"
                ),
            )
        )
        result = MailSender(
            receivers=[self.username],
            title="【蓝鲸审计中心】风险数据导出结果通知",
            content=content,
            attachments=[attachment],
        ).send()
        logger.info(
            "[RiskExportService] send mail finished username=%s total=%s filename=%s result=%s",
            self.username,
            export_file.total,
            export_file.filename,
            result,
        )
        return result
