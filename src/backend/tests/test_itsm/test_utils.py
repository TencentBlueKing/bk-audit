# -*- coding: utf-8 -*-
from django.test import SimpleTestCase

from apps.itsm.utils import parse_v4_workflow_fields, resolve_field_type

# 前端 process-application-manage/create/index.vue 套餐配置页识别的字段类型：
# SELECT（带选项）、TEXT（多行 textarea）、其余单行输入
FRONTEND_TYPE_BRANCHES = {"SELECT", "TEXT"}


class TestResolveFieldType(SimpleTestCase):
    def test_textarea_maps_to_frontend_text(self):
        """V4 textarea 必须映射为前端契约 TEXT，否则丢失多行输入能力"""

        field_type = resolve_field_type({}, {"type": "textarea"})

        self.assertEqual(field_type, "TEXT")
        self.assertIn(field_type, FRONTEND_TYPE_BRANCHES)

    def test_text_maps_to_string(self):
        """V3 的 text 与 input 同属单行 STRING，前端走 v-else 单行输入，符合契约"""

        field_type = resolve_field_type({}, {"type": "text"})

        self.assertEqual(field_type, "STRING")

    def test_input_maps_to_string(self):
        field_type = resolve_field_type({}, {"type": "input"})

        self.assertEqual(field_type, "STRING")

    def test_select_with_choice_maps_to_select(self):
        field_type = resolve_field_type({"itsm_options": [{"key": "a", "name": "A"}]}, {"type": "select"})

        self.assertEqual(field_type, "SELECT")
        self.assertIn(field_type, FRONTEND_TYPE_BRANCHES)


class TestParseV4WorkflowFields(SimpleTestCase):
    def test_textarea_field_type_is_frontend_text(self):
        workflow = {
            "form_canvas_data": {
                "jsonschema": {
                    "properties": {
                        "desc": {"title": "描述"},
                    }
                },
                "form_data": {
                    "layout": [
                        {
                            "list": [
                                {"key": "desc", "name": "描述", "type": "textarea"},
                            ]
                        }
                    ]
                },
            },
        }

        fields = parse_v4_workflow_fields(workflow)

        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]["key"], "desc")
        self.assertEqual(fields[0]["type"], "TEXT")
