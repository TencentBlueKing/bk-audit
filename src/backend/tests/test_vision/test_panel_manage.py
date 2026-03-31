# -*- coding: utf-8 -*-
from unittest.mock import patch

from django.test import TestCase

from core.models import UUIDField
from services.web.vision.models import (
    ReportGroup,
    ReportUserPreference,
    Scenario,
    VisionPanel,
)
from services.web.vision.resources.panel import (
    CreatePanel,
    DeletePanel,
    GetPanelPreference,
    ListManagePanels,
    UpdateGroupOrder,
    UpdatePanel,
    UpdatePanelOrder,
    UpdatePanelPreference,
)


class TestGroupAutoManagement(TestCase):
    def test_get_or_create_by_name_creates_new(self):
        group = ReportGroup.get_or_create_by_name("测试分组")
        self.assertEqual(group.name, "测试分组")
        self.assertTrue(ReportGroup.objects.filter(name="测试分组").exists())

    def test_get_or_create_by_name_returns_existing(self):
        existing = ReportGroup.objects.create(name="已有分组", priority_index=0)
        group = ReportGroup.get_or_create_by_name("已有分组")
        self.assertEqual(group.id, existing.id)

    def test_cleanup_empty_removes_empty(self):
        empty_group = ReportGroup.objects.create(name="空分组", priority_index=0)
        used_group = ReportGroup.objects.create(name="有 Panel 的分组", priority_index=1)
        VisionPanel.objects.create(
            id=UUIDField.get_default_value(),
            name="test",
            group=used_group,
            scenario=Scenario.DEFAULT,
        )
        ReportGroup.cleanup_empty()
        self.assertFalse(ReportGroup.objects.filter(id=empty_group.id).exists())
        self.assertTrue(ReportGroup.objects.filter(id=used_group.id).exists())

    def test_cleanup_empty_ignores_soft_deleted_panels(self):
        group = ReportGroup.objects.create(name="软删除分组", priority_index=0)
        panel = VisionPanel.objects.create(
            id=UUIDField.get_default_value(),
            name="soft_del",
            group=group,
            scenario=Scenario.DEFAULT,
        )
        panel.delete()
        ReportGroup.cleanup_empty()
        self.assertFalse(ReportGroup.objects.filter(id=group.id).exists())


class TestCreatePanel(TestCase):
    def test_create_panel_default_enabled(self):
        resp = CreatePanel().request(
            {
                "vision_id": "share_123",
                "name": "测试报表",
                "group_name": "新分组",
                "description": "描述",
            }
        )
        self.assertEqual(resp["name"], "测试报表")
        self.assertEqual(resp["vision_id"], "share_123")
        self.assertEqual(resp["group_name"], "新分组")
        self.assertTrue(resp["is_enabled"])
        self.assertTrue(ReportGroup.objects.filter(name="新分组").exists())

    def test_create_panel_explicit_disabled(self):
        resp = CreatePanel().request(
            {
                "vision_id": "share_456",
                "name": "禁用报表",
                "group_name": "分组",
                "is_enabled": False,
            }
        )
        self.assertFalse(resp["is_enabled"])

    def test_create_panel_existing_group(self):
        ReportGroup.objects.create(name="已有分组", priority_index=5)
        resp = CreatePanel().request({"vision_id": "share_789", "name": "新报表", "group_name": "已有分组"})
        self.assertEqual(resp["group_name"], "已有分组")
        self.assertEqual(ReportGroup.objects.filter(name="已有分组").count(), 1)

    def test_create_panel_response_fields(self):
        resp = CreatePanel().request({"vision_id": "share_f", "name": "字段检查", "group_name": "F分组"})
        expected_fields = {
            "id",
            "name",
            "description",
            "vision_id",
            "is_enabled",
            "priority_index",
            "group_id",
            "group_name",
            "group_priority_index",
            "updated_by",
            "updated_at",
        }
        self.assertEqual(set(resp.keys()), expected_fields)


class TestUpdatePanel(TestCase):
    def setUp(self):
        self.group = ReportGroup.objects.create(name="原分组", priority_index=0)
        self.panel = VisionPanel.objects.create(
            id="test_panel_1",
            name="原名称",
            vision_id="share_1",
            group=self.group,
            scenario=Scenario.DEFAULT,
            is_enabled=False,
        )

    def test_update_name(self):
        resp = UpdatePanel().request({"id": "test_panel_1", "name": "新名称"})
        self.assertEqual(resp["name"], "新名称")
        self.panel.refresh_from_db()
        self.assertEqual(self.panel.name, "新名称")

    def test_update_is_enabled(self):
        resp = UpdatePanel().request({"id": "test_panel_1", "is_enabled": True})
        self.assertTrue(resp["is_enabled"])
        self.panel.refresh_from_db()
        self.assertTrue(self.panel.is_enabled)

    def test_update_group_triggers_cleanup(self):
        UpdatePanel().request({"id": "test_panel_1", "group_name": "新分组"})
        self.panel.refresh_from_db()
        self.assertEqual(self.panel.group.name, "新分组")
        self.assertFalse(ReportGroup.objects.filter(name="原分组").exists())

    def test_update_multiple_fields(self):
        resp = UpdatePanel().request({"id": "test_panel_1", "name": "新名称", "description": "新描述", "is_enabled": True})
        self.assertEqual(resp["name"], "新名称")
        self.assertEqual(resp["description"], "新描述")
        self.assertTrue(resp["is_enabled"])

    def test_update_nonexistent_panel_404(self):
        with self.assertRaises(Exception):
            UpdatePanel().request({"id": "nonexistent", "name": "x"})


class TestDeletePanel(TestCase):
    def setUp(self):
        self.group = ReportGroup.objects.create(name="待清理分组", priority_index=0)
        self.panel = VisionPanel.objects.create(
            id="del_panel_1",
            name="待删除",
            group=self.group,
            scenario=Scenario.DEFAULT,
        )

    def test_delete_panel_cleans_up_group(self):
        DeletePanel().request({"id": "del_panel_1"})
        self.assertTrue(VisionPanel._objects.get(id="del_panel_1").is_deleted)
        self.assertFalse(ReportGroup.objects.filter(name="待清理分组").exists())

    def test_delete_nonexistent_panel_404(self):
        with self.assertRaises(Exception):
            DeletePanel().request({"id": "nonexistent"})

    def test_delete_keeps_group_with_other_panels(self):
        VisionPanel.objects.create(
            id="del_panel_2",
            name="保留",
            group=self.group,
            scenario=Scenario.DEFAULT,
        )
        DeletePanel().request({"id": "del_panel_1"})
        self.assertTrue(ReportGroup.objects.filter(name="待清理分组").exists())


class TestUpdatePanelOrder(TestCase):
    def setUp(self):
        self.group_a = ReportGroup.objects.create(name="分组A", priority_index=1)
        self.group_b = ReportGroup.objects.create(name="分组B", priority_index=0)
        self.panel_1 = VisionPanel.objects.create(
            id="order_p1", name="P1", group=self.group_a, scenario=Scenario.DEFAULT, priority_index=0
        )
        self.panel_2 = VisionPanel.objects.create(
            id="order_p2", name="P2", group=self.group_a, scenario=Scenario.DEFAULT, priority_index=1
        )

    def test_reorder_within_group(self):
        UpdatePanelOrder().request(
            {
                "panels": [
                    {"id": "order_p1", "group_id": self.group_a.id, "priority_index": 1},
                    {"id": "order_p2", "group_id": self.group_a.id, "priority_index": 0},
                ]
            }
        )
        self.panel_1.refresh_from_db()
        self.panel_2.refresh_from_db()
        self.assertEqual(self.panel_1.priority_index, 1)
        self.assertEqual(self.panel_2.priority_index, 0)

    def test_cross_group_move_cleans_up(self):
        UpdatePanelOrder().request(
            {
                "panels": [
                    {"id": "order_p1", "group_id": self.group_b.id, "priority_index": 0},
                    {"id": "order_p2", "group_id": self.group_b.id, "priority_index": 1},
                ]
            }
        )
        self.assertFalse(ReportGroup.objects.filter(id=self.group_a.id).exists())

    def test_invalid_panel_id_raises_error(self):
        with self.assertRaises(Exception) as ctx:
            UpdatePanelOrder().request(
                {"panels": [{"id": "nonexistent", "group_id": self.group_a.id, "priority_index": 0}]}
            )
        self.assertIn("nonexistent", str(ctx.exception))

    def test_reorder_does_not_update_updated_by(self):
        old_updated_by = self.panel_1.updated_by
        UpdatePanelOrder().request(
            {
                "panels": [
                    {"id": "order_p1", "group_id": self.group_a.id, "priority_index": 10},
                    {"id": "order_p2", "group_id": self.group_a.id, "priority_index": 5},
                ]
            }
        )
        self.panel_1.refresh_from_db()
        self.assertEqual(self.panel_1.updated_by, old_updated_by)


class TestUpdateGroupOrder(TestCase):
    def setUp(self):
        self.group_a = ReportGroup.objects.create(name="A", priority_index=0)
        self.group_b = ReportGroup.objects.create(name="B", priority_index=1)
        VisionPanel.objects.create(id="gp1", name="P1", group=self.group_a, scenario=Scenario.DEFAULT)
        VisionPanel.objects.create(id="gp2", name="P2", group=self.group_b, scenario=Scenario.DEFAULT)

    def test_reorder_groups(self):
        UpdateGroupOrder().request(
            {
                "groups": [
                    {"id": self.group_a.id, "priority_index": 1},
                    {"id": self.group_b.id, "priority_index": 0},
                ]
            }
        )
        self.group_a.refresh_from_db()
        self.group_b.refresh_from_db()
        self.assertEqual(self.group_a.priority_index, 1)
        self.assertEqual(self.group_b.priority_index, 0)

    def test_invalid_group_id_raises_error(self):
        with self.assertRaises(Exception) as ctx:
            UpdateGroupOrder().request({"groups": [{"id": 99999, "priority_index": 0}]})
        self.assertIn("99999", str(ctx.exception))

    def test_reorder_does_not_update_updated_by(self):
        old_updated_by = self.group_a.updated_by
        UpdateGroupOrder().request(
            {
                "groups": [
                    {"id": self.group_a.id, "priority_index": 10},
                    {"id": self.group_b.id, "priority_index": 5},
                ]
            }
        )
        self.group_a.refresh_from_db()
        self.assertEqual(self.group_a.updated_by, old_updated_by)


class TestListManagePanels(TestCase):
    def setUp(self):
        self.group = ReportGroup.objects.create(name="测试分组", priority_index=1)
        self.panel_a = VisionPanel.objects.create(
            id="list_p1",
            name="Panel A",
            group=self.group,
            scenario=Scenario.DEFAULT,
            is_enabled=True,
            priority_index=1,
        )
        self.panel_b = VisionPanel.objects.create(
            id="list_p2",
            name="Panel B",
            group=self.group,
            scenario=Scenario.DEFAULT,
            is_enabled=False,
            priority_index=0,
        )

    def test_list_returns_serialized_flat_list(self):
        resp = ListManagePanels().request({"keyword": "", "is_enabled": None})
        our_panels = [p for p in resp if p["group_id"] == self.group.id]
        self.assertEqual(len(our_panels), 2)
        self.assertIn("group_priority_index", our_panels[0])

    def test_filter_by_is_enabled(self):
        resp = ListManagePanels().request({"keyword": "", "is_enabled": True})
        our_panels = [p for p in resp if p["group_id"] == self.group.id]
        self.assertEqual(len(our_panels), 1)
        self.assertEqual(our_panels[0]["id"], "list_p1")

    def test_search_by_keyword(self):
        resp = ListManagePanels().request({"keyword": "Panel A"})
        our_panels = [p for p in resp if p["group_id"] == self.group.id]
        self.assertEqual(len(our_panels), 1)
        self.assertEqual(our_panels[0]["name"], "Panel A")

    def test_ordered_by_group_then_panel_priority(self):
        group_b = ReportGroup.objects.create(name="低优先级分组", priority_index=0)
        VisionPanel.objects.create(
            id="list_p3",
            name="Panel C",
            group=group_b,
            scenario=Scenario.DEFAULT,
            priority_index=10,
        )
        resp = ListManagePanels().request({"keyword": "", "is_enabled": None})
        our_ids = [p["id"] for p in resp if p["id"].startswith("list_")]
        self.assertEqual(our_ids, ["list_p1", "list_p2", "list_p3"])

    def test_default_params_via_serializer(self):
        resp = ListManagePanels().request({})
        self.assertIsInstance(resp, list)


class TestPanelPreference(TestCase):
    @patch("services.web.vision.resources.panel.get_request_username", return_value="testuser")
    def test_get_creates_default(self, _):
        resp = GetPanelPreference().request({})
        self.assertEqual(resp["config"], {})

    @patch("services.web.vision.resources.panel.get_request_username", return_value="testuser")
    def test_update_overwrites(self, _):
        ReportUserPreference.objects.create(username="testuser", config={"old": True})
        resp = UpdatePanelPreference().request({"config": {"collapsed": [1, 2]}})
        self.assertEqual(resp["config"], {"collapsed": [1, 2]})

    @patch("services.web.vision.resources.panel.get_request_username", return_value="testuser")
    def test_get_after_update_returns_latest(self, _):
        UpdatePanelPreference().request({"config": {"key": "val"}})
        resp = GetPanelPreference().request({})
        self.assertEqual(resp["config"], {"key": "val"})


class TestFullCRUDFlow(TestCase):
    """端到端链路：创建 → 列表 → 更新 → 排序 → 删除"""

    def test_full_lifecycle(self):
        # 创建两个 Panel
        p1 = CreatePanel().request({"vision_id": "v1", "name": "报表1", "group_name": "分组A"})
        p2 = CreatePanel().request({"vision_id": "v2", "name": "报表2", "group_name": "分组A"})
        self.assertEqual(p1["group_name"], "分组A")
        self.assertEqual(p2["group_name"], "分组A")
        group_id = p1["group_id"]

        # 列表能看到
        panels = ListManagePanels().request({})
        our = [p for p in panels if p["group_id"] == group_id]
        self.assertEqual(len(our), 2)

        # 更新名称 + 启停
        updated = UpdatePanel().request({"id": p1["id"], "name": "新报表1", "is_enabled": False})
        self.assertEqual(updated["name"], "新报表1")
        self.assertFalse(updated["is_enabled"])

        # 更新分组（触发自动创建新分组）
        updated2 = UpdatePanel().request({"id": p2["id"], "group_name": "分组B"})
        self.assertEqual(updated2["group_name"], "分组B")
        self.assertTrue(ReportGroup.objects.filter(name="分组A").exists())

        # 排序
        new_group_id = updated2["group_id"]
        UpdatePanelOrder().request(
            {
                "panels": [
                    {"id": p1["id"], "group_id": new_group_id, "priority_index": 1},
                    {"id": p2["id"], "group_id": new_group_id, "priority_index": 0},
                ]
            }
        )
        self.assertFalse(ReportGroup.objects.filter(id=group_id).exists())

        # 删除
        DeletePanel().request({"id": p1["id"]})
        panels_after = ListManagePanels().request({})
        remaining = [p for p in panels_after if p["id"] == p1["id"]]
        self.assertEqual(len(remaining), 0)

        # 再删 p2，分组自动清理
        DeletePanel().request({"id": p2["id"]})
        self.assertFalse(ReportGroup.objects.filter(name="分组B").exists())
