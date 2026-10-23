# -*- coding: utf-8 -*-
from django.test import SimpleTestCase
from jsonschema import Draft7Validator

from apps.itsm.utils import parse_v4_workflow_fields, resolve_field_type
from services.web.databus.collector.snapshot.system.base import v3_field_to_jsonschema

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


class TestV3FieldToJsonschema(SimpleTestCase):
    """V3 字段 -> V4 JSON Schema 转换。

    reviewer P1：V3 字段类型（如 STRING/INT/SELECT）不能直接用作 JSON Schema 的 type，
    否则生成 {"type":"STRING"} 等非法 schema，导致有正常历史表单的迁移失败。
    这里覆盖普通文本、数字、单选项、多选项、人员、富文本、日期等典型类型，
    并用 Draft7Validator.check_schema 复现/防止 SchemaError。
    """

    def test_string_field_maps_to_lowercase_string(self):
        prop = v3_field_to_jsonschema({"key": "title", "name": "标题", "type": "STRING"})

        self.assertEqual(prop, {"title": "标题", "type": "string"})

    def test_int_field_maps_to_number(self):
        prop = v3_field_to_jsonschema({"key": "count", "name": "次数", "type": "INT"})

        self.assertEqual(prop["type"], "number")

    def test_text_field_maps_to_string_with_textarea_format(self):
        prop = v3_field_to_jsonschema({"key": "desc", "name": "描述", "type": "TEXT"})

        self.assertEqual(prop, {"title": "描述", "type": "string", "format": "textarea"})

    def test_richtext_maps_to_richtext_format(self):
        prop = v3_field_to_jsonschema({"key": "content", "name": "正文", "type": "RICHTEXT"})

        self.assertEqual(prop, {"title": "正文", "type": "string", "format": "richText"})

    def test_date_and_datetime_use_formats(self):
        date_prop = v3_field_to_jsonschema({"key": "d", "name": "日期", "type": "DATE"})
        datetime_prop = v3_field_to_jsonschema({"key": "dt", "name": "时间", "type": "DATETIME"})

        self.assertEqual(date_prop, {"title": "日期", "type": "string", "format": "date"})
        self.assertEqual(datetime_prop, {"title": "时间", "type": "string", "format": "date-time"})

    def test_select_carries_enum(self):
        """单选 / 下拉：type=string + enum 约束（V4 据此渲染下拉）"""

        field = {
            "key": "level",
            "name": "等级",
            "type": "SELECT",
            "choice": [{"key": "high", "name": "高"}, {"key": "low", "name": "低"}],
        }
        prop = v3_field_to_jsonschema(field)

        self.assertEqual(prop["type"], "string")
        self.assertEqual(set(prop["enum"]), {"high", "low"})

    def test_radio_carries_enum_like_select(self):
        field = {
            "key": "mode",
            "name": "模式",
            "type": "RADIO",
            "choice": [{"key": "a", "name": "A"}, {"key": "b", "name": "B"}],
        }
        prop = v3_field_to_jsonschema(field)

        self.assertEqual(prop["type"], "string")
        self.assertEqual(set(prop["enum"]), {"a", "b"})

    def test_multiselect_maps_to_array_with_string_items(self):
        """多选：type=array + items.string（V4 据此渲染多选下拉）"""

        prop = v3_field_to_jsonschema({"key": "tags", "name": "标签", "type": "MULTISELECT"})

        self.assertEqual(prop, {"title": "标签", "type": "array", "items": {"type": "string"}})

    def test_checkbox_maps_to_array(self):
        prop = v3_field_to_jsonschema({"key": "agree", "name": "同意", "type": "CHECKBOX"})

        self.assertEqual(prop, {"title": "同意", "type": "array", "items": {"type": "string"}})

    def test_members_maps_to_array_with_user_format(self):
        """多选人员：array + items.format=user（SDK 文档「多选用户」）"""

        prop = v3_field_to_jsonschema({"key": "owners", "name": "负责人", "type": "MEMBERS"})

        self.assertEqual(prop, {"title": "负责人", "type": "array", "items": {"type": "string", "format": "user"}})

    def test_unknown_type_falls_back_to_string(self):
        """未知类型不应抛错，缺省 string，避免迁移中断"""

        prop = v3_field_to_jsonschema({"key": "x", "name": "X", "type": "NOT_A_REAL_TYPE"})

        self.assertEqual(prop["type"], "string")

    def test_full_form_schema_is_draft7_valid(self):
        """完整 form_schema（含多种真实 V3 历史字段）必须通过 Draft7 schema 校验。

        reviewer 用 Draft7Validator.check_schema 复现过 {"type":"STRING"} 的 SchemaError，
        本用例确保正常历史表单迁移生成的 schema 合法。
        """

        v3_fields = [
            {"key": "title", "name": "标题", "type": "STRING"},
            {"key": "count", "name": "次数", "type": "INT"},
            {"key": "desc", "name": "描述", "type": "TEXT"},
            {"key": "level", "name": "等级", "type": "SELECT", "choice": [{"key": "h", "name": "高"}]},
            {"key": "tags", "name": "标签", "type": "MULTISELECT"},
            {"key": "owners", "name": "负责人", "type": "MEMBERS"},
            {"key": "d", "name": "日期", "type": "DATE"},
        ]
        properties = {f["key"]: v3_field_to_jsonschema(f) for f in v3_fields}
        form_schema = {"type": "object", "required": ["title"], "properties": properties}

        # 不抛 SchemaError 即通过；同时显式校验无错误
        Draft7Validator.check_schema(form_schema)
        errors = list(Draft7Validator(form_schema).iter_errors({"title": "t", "count": 1}))
        self.assertEqual(errors, [])
