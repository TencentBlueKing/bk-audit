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

import time

from bk_resource import api
from blueapps.utils.logger import logger
from django.conf import settings

from api.bk_log.constants import INDEX_SET_ID
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.analyze.controls.base import Controller
from services.web.databus.constants import PluginSceneChoices
from services.web.databus.models import CollectorPlugin
from services.web.strategy_v2.constants import StrategyAlertLevel, StrategyStatusChoices


class BKMController(Controller):
    """
    Control BKM Strategy
    """

    def create(self) -> None:
        return self._save_strategy()

    def update(self) -> None:
        return self._save_strategy()

    def delete(self) -> None:
        params = {"bk_biz_id": settings.DEFAULT_BK_BIZ_ID, "ids": [self.strategy.backend_data["id"]]}
        api.bk_monitor.delete_alarm_strategy(**params)
        self.strategy.status = StrategyStatusChoices.DISABLED.value
        self.strategy.save(update_record=False, update_fields=["status"])

    def enable(self) -> None:
        self._toggle_strategy(True)

    def disabled(self) -> None:
        self._toggle_strategy(False)

    def _save_strategy(self) -> None:
        try:
            params = self._build_bkm_params()
            result = api.bk_monitor.save_alarm_strategy(**params)
            self.strategy.backend_data = result
            self.strategy.status = StrategyStatusChoices.RUNNING.value
            self.strategy.save(update_record=False, update_fields=["backend_data", "status"])
        except Exception as err:  # NOCC:broad-except(需要处理所有异常)
            logger.error("[CreateBKMStrategyFailed] %s", err)
            self.strategy.status = StrategyStatusChoices.FAILED.value
            self.strategy.save(update_record=False, update_fields=["status"])

    def _toggle_strategy(self, status: bool):
        params = {"is_enabled": status, "ids": [self.strategy.backend_data["id"]]}
        api.bk_monitor.switch_alarm_strategy(params)
        self.strategy.status = StrategyStatusChoices.RUNNING.value if status else StrategyStatusChoices.DISABLED.value
        self.strategy.save(update_record=False, update_fields=["status"])

    def _build_bkm_params(self) -> dict:
        name = self._build_name()
        index_set_id = self._get_index_set_id(self.strategy.namespace)
        result_table_id = self._get_table_id(self.strategy.namespace)
        params = {
            "bk_biz_id": settings.DEFAULT_BK_BIZ_ID,
            "name": name,
            "source": "bkmonitorv3",
            "scenario": "application_check",
            "type": "monitor",
            "items": [
                {
                    "name": name,
                    "no_data_config": {"is_enabled": False},
                    "target": [[]],
                    "expression": "a",
                    "functions": [],
                    "origin_sql": "",
                    "query_configs": [
                        {
                            "data_source_label": "bk_log_search",
                            "data_type_label": "log",
                            "alias": "a",
                            "metric_id": "bk_log_search.index_set.{}".format(index_set_id),
                            "functions": [],
                            "query_string": "*",
                            "result_table_id": result_table_id,
                            "index_set_id": index_set_id,
                            "agg_interval": self.strategy.configs["agg_interval"],
                            "agg_dimension": self.strategy.configs["agg_dimension"],
                            "agg_condition": self.strategy.configs["agg_condition"],
                            "time_field": "dtEventTimeStamp",
                            "name": result_table_id,
                        }
                    ],
                    "algorithms": [
                        {
                            "type": "Threshold",
                            "level": "2",  # warning
                            "config": [[{"method": algorithms["method"], "threshold": algorithms["threshold"]}]],
                            "unit_prefix": "",
                        }
                        for algorithms in self.strategy.configs["algorithms"]
                    ],
                }
            ],
            "detects": [
                {
                    "level": level,
                    "expression": "",
                    "trigger_config": {
                        "count": self.strategy.configs["detects"]["count"],
                        "uptime": {
                            "calendars": [],
                            "time_ranges": [
                                {
                                    "end": "23:59",
                                    "start": "00:00",
                                }
                            ],
                        },
                        "check_window": self.strategy.configs["detects"]["alert_window"],
                    },
                    "recovery_config": {
                        "check_window": 1,
                        "status_setter": "recovery",
                    },
                    "connector": "and",
                }
                for level in StrategyAlertLevel.values
            ],
            "actions": [],
            "notice": {
                "user_groups": [],
                "signal": ["abnormal", "closed"],
                "options": {"converge_config": {}},
                "relate_type": "NOTICE",
                "config": {
                    "template": [
                        {
                            "signal": signal,
                            "message_tmpl": (
                                "{{content.level}}\n"
                                "{{content.begin_time}}\n"
                                "{{content.time}}\n"
                                "{{content.duration}}\n"
                                "{{content.target_type}}\n"
                                "{{content.data_source}}\n"
                                "{{content.content}}\n"
                                "{{content.current_value}}\n"
                                "{{content.biz}}\n"
                                "{{content.target}}\n"
                                "{{content.dimension}}\n"
                                "{{content.detail}}"
                            ),
                            "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                        }
                        for signal in ["abnormal", "closed"]
                    ]
                },
            },
            "labels": [],
            "is_enabled": self.strategy.backend_data.get("is_enabled", True),
        }
        if self.strategy.backend_data.get("id"):
            params["id"] = self.strategy.backend_data["id"]
        return params

    def _get_table_id(self, namespace: str) -> str:
        plugin = (
            CollectorPlugin.objects.filter(namespace=namespace, plugin_scene=PluginSceneChoices.COLLECTOR.value)
            .order_by("-collector_plugin_id")
            .first()
        )
        table_id = "{}_bklog.{}".format(settings.DEFAULT_BK_BIZ_ID, plugin.collector_plugin_name_en.lower())
        return table_id

    def _get_index_set_id(self, namespace: str) -> str:
        return GlobalMetaConfig.get(
            INDEX_SET_ID, config_level=ConfigLevelChoices.NAMESPACE.value, instance_key=namespace
        )

    def _build_name(self) -> str:
        return self.strategy.backend_data.get("name") or "BkAudit_{}".format(time.time_ns())
