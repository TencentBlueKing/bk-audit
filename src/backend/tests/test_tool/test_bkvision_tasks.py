from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from services.web.tool.constants import ToolTypeEnum
from services.web.tool.models import BkVisionToolConfig, Tool
from services.web.tool.tasks import update_bkvision_config
from services.web.vision.models import Scenario, VisionPanel


class UpdateBkVisionConfigTaskTestCase(TestCase):
    def setUp(self):
        self.filter_uid = "filter_uid"
        self.custom_filter_uid = "custom_filter_uid"
        self.variable_uid = "variable_uid"
        self.variable_flag = "variable_flag"

        # 为工具创建对应的 VisionPanel 配置
        self.panel = VisionPanel.objects.create(
            id="panel-id",
            vision_id="vision",
            name="panel",
            scenario=Scenario.TOOL.value,
            handler="CommonVisionHandler",
        )
        self.tool = Tool.objects.create(
            uid="tool-uid",
            version=1,
            name="bkvision tool",
            namespace="default",
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={
                "uid": "bkvision-dashboard",
                "input_variable": [
                    {
                        "raw_name": "time_range",
                        "description": self.filter_uid,
                        "display_name": "时间范围",
                        "field_category": "time-ranger",
                        "required": True,
                        "is_default_value": True,
                        "default_value": ["now-1d/d", "now"],
                    },
                    {
                        "raw_name": "system",
                        "description": self.custom_filter_uid,
                        "display_name": "系统",
                        "field_category": "selector",
                        "required": False,
                        "is_default_value": False,
                        "default_value": "custom",
                    },
                    {
                        "raw_name": "white_list",
                        "description": self.variable_uid,
                        "display_name": "白名单",
                        "field_category": "variable",
                        "required": True,
                        "is_default_value": True,
                        "default_value": ["a"],
                    },
                ],
            },
            permission_owner="tester",
        )
        # 绑定工具与面板，写入初始更新时间
        BkVisionToolConfig.objects.create(
            tool=self.tool,
            panel=self.panel,
            updated_time=timezone.now(),
        )

        # QueryMeta filters 的默认结构
        self.filters_template = {
            self.filter_uid: ["now-1d/d", "now"],
            self.custom_filter_uid: "meta-custom",
        }
        # QueryMeta constants 中非内置变量默认值
        self.constants_template = {
            self.variable_flag: ["a"],
        }
        # QueryMeta variables 列表（包含一个非内置，一个内置）
        self.variables_template = [
            {
                "uid": self.variable_uid,
                "flag": self.variable_flag,
                "build_in": False,
            },
            {
                "uid": "built-in",
                "flag": "built-in-flag",
                "build_in": True,
            },
        ]

    def build_meta(self, *, filters=None, constants=None, variables=None):
        return {
            "data": {
                # QueryMeta 返回的变量信息
                "variables": variables
                if variables is not None
                else list(self.variables_template),
            },
            # 交互组件默认值
            "filters": filters if filters is not None else dict(self.filters_template),
            # 变量默认值（仅关注非内置变量）
            "constants": constants if constants is not None else dict(self.constants_template),
        }

    @patch("services.web.tool.tasks.api.bk_vision.query_meta")
    def test_no_update_when_meta_matches(self, query_meta):
        query_meta.return_value = self.build_meta()

        update_bkvision_config()

        self.tool.refresh_from_db()
        self.assertFalse(self.tool.is_bkvision)

    @patch("services.web.tool.tasks.api.bk_vision.query_meta")
    def test_update_when_filter_default_differs(self, query_meta):
        filters = dict(self.filters_template)
        filters[self.filter_uid] = ["now-2d/d", "now-1d/d"]
        query_meta.return_value = self.build_meta(filters=filters)

        update_bkvision_config()

        self.tool.refresh_from_db()
        self.assertTrue(self.tool.is_bkvision)

    @patch("services.web.tool.tasks.api.bk_vision.query_meta")
    def test_update_when_meta_missing_required_filter(self, query_meta):
        filters = {self.custom_filter_uid: "meta-custom"}
        query_meta.return_value = self.build_meta(filters=filters)

        update_bkvision_config()

        self.tool.refresh_from_db()
        self.assertTrue(self.tool.is_bkvision)

    @patch("services.web.tool.tasks.api.bk_vision.query_meta")
    def test_custom_value_field_does_not_trigger_update(self, query_meta):
        filters = dict(self.filters_template)
        filters[self.custom_filter_uid] = "diff-custom"
        query_meta.return_value = self.build_meta(filters=filters)

        update_bkvision_config()

        self.tool.refresh_from_db()
        self.assertFalse(self.tool.is_bkvision)

    @patch("services.web.tool.tasks.api.bk_vision.query_meta")
    def test_keep_flag_when_already_marked_and_meta_still_differs(self, query_meta):
        """已标记更新且差异仍存在时应保持 True 不回写。"""

        filters = dict(self.filters_template)
        filters[self.filter_uid] = ["now-2d/d", "now-1d/d"]
        query_meta.return_value = self.build_meta(filters=filters)

        self.tool.is_bkvision = True
        self.tool.save(update_record=False, update_fields=["is_bkvision"])

        update_bkvision_config()

        self.tool.refresh_from_db()
        self.assertTrue(self.tool.is_bkvision)

    @patch("services.web.tool.tasks.api.bk_vision.query_meta")
    def test_reset_flag_when_meta_matches(self, query_meta):
        """已标记更新且差异消失时应恢复为 False。"""

        query_meta.return_value = self.build_meta()

        self.tool.is_bkvision = True
        self.tool.save(update_record=False, update_fields=["is_bkvision"])

        update_bkvision_config()

        self.tool.refresh_from_db()
        self.assertFalse(self.tool.is_bkvision)
