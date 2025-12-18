# -*- coding: utf-8 -*-
"""
验证 AIOpsController 在更新/创建 BKBase Flow 时，ES 与 Doris 存储节点均并联到场景方案节点（scenario_app），
而不是串到彼此后面。
"""
import json
from datetime import datetime as RealDatetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

from services.web.analyze.controls.aiops import AIOpsController


class DummyStrategy(SimpleNamespace):
    def save(self, *args, **kwargs):
        return None


class TestAiopsFlowLinks(TestCase):
    @patch("services.web.analyze.controls.aiops.api.bk_base.update_flow_node")
    @patch("services.web.analyze.controls.aiops.api.bk_base.create_flow_node")
    def test_storage_nodes_link_to_scenario(self, mock_create: MagicMock, mock_update: MagicMock):
        # 预置 create_flow_node 返回的 node_id 顺序：
        # 1) 数据源、2) SQL、3) 场景、4) ES、5) Doris
        node_ids = [101, 102, 103, 104, 105]

        def _create_side_effect(**kwargs):
            return {"node_id": node_ids.pop(0)}

        mock_create.side_effect = _create_side_effect
        mock_update.return_value = {"node_id": 999}

        controller = AIOpsController.__new__(AIOpsController)
        controller.strategy = DummyStrategy(backend_data={"flow_id": 1})

        # 构造受控的节点集合，避免依赖真实 _build_flow_nodes 复杂逻辑
        def _fake_build_flow_nodes():
            return [
                {"node_type": "stream_source", "name": "src"},
                {"node_type": "realtime", "name": "sql"},
                {"node_type": "scenario_app", "name": "scene", "outputs": [{}], "inputs": [{}]},
                {"node_type": "elastic_storage", "name": "es", "from_result_table_ids": ["2_scenario_rt"]},
                {"node_type": "doris", "name": "doris", "from_result_table_ids": ["2_scenario_rt"]},
            ]

        controller._build_flow_nodes = _fake_build_flow_nodes  # type: ignore

        # 固定时间戳，确保 from_links.target.id 可预测
        class FixedDatetime(RealDatetime):
            @classmethod
            def now(cls, tz=None):
                return cls.fromtimestamp(1739900000)  # 2025-02-19T00:13:20Z

        with patch("services.web.analyze.controls.aiops.datetime.datetime", FixedDatetime):
            controller._update_or_create_bkbase_flow()

        # 第三次 create 调用对应场景节点，拿到的 node_id 应为 103
        scenario_node_id = 103

        # 第四、五次调用分别对应 ES 与 Doris
        self.assertGreaterEqual(mock_create.call_count, 5)
        es_call = mock_create.call_args_list[3].kwargs
        doris_call = mock_create.call_args_list[4].kwargs

        fixed_ms = int(FixedDatetime.now().timestamp() * 1000)

        # 构造期望的完整 JSON 负载，并做全量 JSON 等值断言
        expected_es_payload = {
            "flow_id": 1,
            "frontend_info": {"x": 1200, "y": 30},
            "from_links": [
                {
                    "source": {"node_id": scenario_node_id, "id": f"ch_{scenario_node_id}", "arrow": "Left"},
                    "target": {"id": f"bk_node_{fixed_ms}", "arrow": "Left"},
                }
            ],
            "node_type": "elastic_storage",
            "config": {
                "node_type": "elastic_storage",
                "name": "es",
                "from_result_table_ids": ["2_scenario_rt"],
                "node_id": 104,
            },
        }

        expected_doris_payload = {
            "flow_id": 1,
            "frontend_info": {"x": 1500, "y": 30},
            "from_links": [
                {
                    "source": {"node_id": scenario_node_id, "id": f"ch_{scenario_node_id}", "arrow": "Left"},
                    "target": {"id": f"bk_node_{fixed_ms}", "arrow": "Left"},
                }
            ],
            "node_type": "doris",
            "config": {
                "node_type": "doris",
                "name": "doris",
                "from_result_table_ids": ["2_scenario_rt"],
                "node_id": 105,
            },
        }

        self.assertJSONEqual(
            json.dumps(es_call, ensure_ascii=False), json.dumps(expected_es_payload, ensure_ascii=False)
        )
        self.assertJSONEqual(
            json.dumps(doris_call, ensure_ascii=False), json.dumps(expected_doris_payload, ensure_ascii=False)
        )
