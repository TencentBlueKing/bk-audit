# -*- coding: utf-8 -*-
from unittest.mock import patch

from django.test import TestCase

from core.models import UUIDField
from services.web.vision.models import (
    ReportGroup,
    ReportUserPreference,
    Scenario,
    UserPanelFavorite,
    VisionPanel,
)
from services.web.vision.resources.panel import (
    CreatePanel,
    DeletePanel,
    GetPanelPreference,
    ListGroups,
    ListManagePanels,
    TogglePanelFavorite,
    UpdateGroup,
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


class TestListGroups(TestCase):
    def setUp(self):
        self.g1 = ReportGroup.objects.create(name="分组A", priority_index=10)
        self.g2 = ReportGroup.objects.create(name="分组B", priority_index=5)

    def test_list_returns_all_groups(self):
        result = ListGroups().request({})
        names = {g["name"] for g in result}
        self.assertIn("分组A", names)
        self.assertIn("分组B", names)

    def test_list_ordered_by_priority_desc(self):
        result = ListGroups().request({})
        our = [g for g in result if g["name"] in ("分组A", "分组B")]
        self.assertEqual(our[0]["name"], "分组A")
        self.assertEqual(our[1]["name"], "分组B")

    def test_list_response_fields(self):
        result = ListGroups().request({})
        group = next(g for g in result if g["id"] == self.g1.id)
        self.assertEqual(group["name"], "分组A")
        self.assertEqual(group["priority_index"], 10)
        self.assertIn("id", group)


class TestUpdateGroup(TestCase):
    def setUp(self):
        self.group = ReportGroup.objects.create(name="原名称", priority_index=5)

    def test_update_name(self):
        resp = UpdateGroup().request({"id": self.group.id, "name": "新名称"})
        self.assertEqual(resp["name"], "新名称")
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, "新名称")

    def test_update_name_preserves_priority(self):
        resp = UpdateGroup().request({"id": self.group.id, "name": "改名"})
        self.assertEqual(resp["priority_index"], 5)

    def test_update_nonexistent_group_404(self):
        with self.assertRaises(Exception):
            UpdateGroup().request({"id": 99999, "name": "不存在"})

    def test_update_duplicate_name_fails(self):
        ReportGroup.objects.create(name="已有名称", priority_index=0)
        with self.assertRaises(Exception):
            UpdateGroup().request({"id": self.group.id, "name": "已有名称"})


class TestTogglePanelFavorite(TestCase):
    def setUp(self):
        self.group = ReportGroup.objects.create(name="收藏测试分组", priority_index=0)
        self.panel = VisionPanel.objects.create(
            id="fav_panel_1",
            name="收藏测试报表",
            group=self.group,
            scenario=Scenario.DEFAULT,
        )

    @patch("services.web.vision.resources.panel.get_request_username", return_value="testuser")
    def test_add_favorite(self, _):
        resp = TogglePanelFavorite().request({"panel_id": "fav_panel_1", "is_favorite": True})
        self.assertTrue(resp["is_favorite"])
        self.assertIsNotNone(resp["favorite_at"])
        self.assertTrue(UserPanelFavorite.objects.filter(username="testuser", panel_id="fav_panel_1").exists())

    @patch("services.web.vision.resources.panel.get_request_username", return_value="testuser")
    def test_remove_favorite(self, _):
        UserPanelFavorite.objects.create(username="testuser", panel=self.panel)
        resp = TogglePanelFavorite().request({"panel_id": "fav_panel_1", "is_favorite": False})
        self.assertFalse(resp["is_favorite"])
        self.assertIsNone(resp["favorite_at"])
        self.assertFalse(UserPanelFavorite.objects.filter(username="testuser", panel_id="fav_panel_1").exists())

    @patch("services.web.vision.resources.panel.get_request_username", return_value="testuser")
    def test_add_favorite_idempotent(self, _):
        TogglePanelFavorite().request({"panel_id": "fav_panel_1", "is_favorite": True})
        resp = TogglePanelFavorite().request({"panel_id": "fav_panel_1", "is_favorite": True})
        self.assertTrue(resp["is_favorite"])
        self.assertEqual(UserPanelFavorite.objects.filter(username="testuser", panel_id="fav_panel_1").count(), 1)

    @patch("services.web.vision.resources.panel.get_request_username", return_value="testuser")
    def test_remove_favorite_idempotent(self, _):
        resp = TogglePanelFavorite().request({"panel_id": "fav_panel_1", "is_favorite": False})
        self.assertFalse(resp["is_favorite"])
        self.assertFalse(UserPanelFavorite.objects.filter(username="testuser", panel_id="fav_panel_1").exists())

    @patch("services.web.vision.resources.panel.get_request_username", return_value="testuser")
    def test_nonexistent_panel_404(self, _):
        with self.assertRaises(Exception):
            TogglePanelFavorite().request({"panel_id": "nonexistent", "is_favorite": True})

    @patch("services.web.vision.resources.panel.get_request_username", return_value="user_a")
    def test_different_users_independent(self, mock_user):
        TogglePanelFavorite().request({"panel_id": "fav_panel_1", "is_favorite": True})
        mock_user.return_value = "user_b"
        TogglePanelFavorite().request({"panel_id": "fav_panel_1", "is_favorite": True})
        self.assertEqual(UserPanelFavorite.objects.filter(panel_id="fav_panel_1").count(), 2)


class TestListPanelsWithFavorite(TestCase):
    def setUp(self):
        self.group = ReportGroup.objects.create(name="收藏列表分组", priority_index=0)
        self.panel_a = VisionPanel.objects.create(
            id="fav_list_p1",
            name="报表A",
            group=self.group,
            scenario=Scenario.DEFAULT,
            is_enabled=True,
        )
        self.panel_b = VisionPanel.objects.create(
            id="fav_list_p2",
            name="报表B",
            group=self.group,
            scenario=Scenario.DEFAULT,
            is_enabled=True,
        )

    @patch("services.web.vision.resources.bkvision.get_request_username", return_value="testuser")
    def test_list_panels_includes_favorite_fields(self, _):
        from services.web.vision.resources.bkvision import ListPanels

        UserPanelFavorite.objects.create(username="testuser", panel=self.panel_a)
        resp = ListPanels().request({"scenario": Scenario.DEFAULT})
        panel_a_data = next(p for p in resp if p["id"] == "fav_list_p1")
        panel_b_data = next(p for p in resp if p["id"] == "fav_list_p2")
        self.assertTrue(panel_a_data["is_favorite"])
        self.assertIsNotNone(panel_a_data["favorite_at"])
        self.assertFalse(panel_b_data["is_favorite"])
        self.assertIsNone(panel_b_data["favorite_at"])

    @patch("services.web.vision.resources.bkvision.get_request_username", return_value="other_user")
    def test_list_panels_no_favorites_all_unfavorite(self, _):
        from services.web.vision.resources.bkvision import ListPanels

        resp = ListPanels().request({"scenario": Scenario.DEFAULT})
        for p in resp:
            if p["id"] in ("fav_list_p1", "fav_list_p2"):
                self.assertFalse(p["is_favorite"])


class TestFullCRUDFlow(TestCase):
    """端到端链路：完整字段校验"""

    MANAGE_PANEL_FIELDS = {
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
    GROUP_FIELDS = {"id", "name", "priority_index"}

    def _assert_dict_contains(self, data, expected):
        for key, val in expected.items():
            self.assertEqual(data[key], val, f"field '{key}': expected {val!r}, got {data[key]!r}")

    def test_full_lifecycle(self):
        # === 创建 ===
        p1 = CreatePanel().request({"vision_id": "v1", "name": "报表1", "group_name": "分组A", "description": "描述1"})
        self.assertEqual(set(p1.keys()), self.MANAGE_PANEL_FIELDS)
        self._assert_dict_contains(
            p1,
            {
                "name": "报表1",
                "vision_id": "v1",
                "description": "描述1",
                "is_enabled": True,
                "group_name": "分组A",
            },
        )
        self.assertIsNotNone(p1["id"])
        self.assertIsNotNone(p1["group_id"])

        p2 = CreatePanel().request(
            {
                "vision_id": "v2",
                "name": "报表2",
                "group_name": "分组A",
                "is_enabled": False,
            }
        )
        self._assert_dict_contains(
            p2,
            {
                "name": "报表2",
                "vision_id": "v2",
                "is_enabled": False,
                "group_name": "分组A",
                "group_id": p1["group_id"],
            },
        )

        group_a_id = p1["group_id"]

        # === 管理端列表 — 扁平、字段完整 ===
        panels = ListManagePanels().request({})
        our = [p for p in panels if p["group_id"] == group_a_id]
        self.assertEqual(len(our), 2)
        for p in our:
            self.assertEqual(set(p.keys()), self.MANAGE_PANEL_FIELDS)

        # 筛选 is_enabled=True
        enabled_only = ListManagePanels().request({"is_enabled": True})
        our_enabled = [p for p in enabled_only if p["group_id"] == group_a_id]
        self.assertEqual(len(our_enabled), 1)
        self.assertEqual(our_enabled[0]["id"], p1["id"])

        # 搜索
        search = ListManagePanels().request({"keyword": "报表2"})
        our_search = [p for p in search if p["group_id"] == group_a_id]
        self.assertEqual(len(our_search), 1)
        self.assertEqual(our_search[0]["id"], p2["id"])

        # === 分组列表 ===
        groups = ListGroups().request({})
        group_a = next(g for g in groups if g["id"] == group_a_id)
        self.assertEqual(set(group_a.keys()), self.GROUP_FIELDS)
        self.assertEqual(group_a["name"], "分组A")

        # === 分组改名 ===
        renamed = UpdateGroup().request({"id": group_a_id, "name": "分组A改名"})
        self._assert_dict_contains(renamed, {"id": group_a_id, "name": "分组A改名"})

        # === 更新 Panel — 名称 + 启停 ===
        updated = UpdatePanel().request({"id": p1["id"], "name": "新报表1", "is_enabled": False})
        self.assertEqual(set(updated.keys()), self.MANAGE_PANEL_FIELDS)
        self._assert_dict_contains(
            updated,
            {
                "id": p1["id"],
                "name": "新报表1",
                "is_enabled": False,
                "group_id": group_a_id,
                "group_name": "分组A改名",
            },
        )

        # === 更新 Panel — 换组（触发自动创建新分组） ===
        updated2 = UpdatePanel().request({"id": p2["id"], "group_name": "分组B"})
        self._assert_dict_contains(updated2, {"name": "报表2", "group_name": "分组B"})
        group_b_id = updated2["group_id"]
        self.assertNotEqual(group_b_id, group_a_id)
        self.assertTrue(ReportGroup.objects.filter(name="分组A改名").exists())

        # === 排序 — 跨组移动 + 空组清理 ===
        UpdatePanelOrder().request(
            {
                "panels": [
                    {"id": p1["id"], "group_id": group_b_id, "priority_index": 10},
                    {"id": p2["id"], "group_id": group_b_id, "priority_index": 5},
                ]
            }
        )
        self.assertFalse(ReportGroup.objects.filter(id=group_a_id).exists())
        p1_db = VisionPanel.objects.get(id=p1["id"])
        self.assertEqual(p1_db.group_id, group_b_id)
        self.assertEqual(p1_db.priority_index, 10)
        p2_db = VisionPanel.objects.get(id=p2["id"])
        self.assertEqual(p2_db.priority_index, 5)

        # === 分组排序 ===
        group_c = ReportGroup.objects.create(name="分组C", priority_index=0)
        VisionPanel.objects.create(id="tmp_c", name="tmp", group=group_c, scenario=Scenario.DEFAULT)
        UpdateGroupOrder().request(
            {
                "groups": [
                    {"id": group_b_id, "priority_index": 0},
                    {"id": group_c.id, "priority_index": 100},
                ]
            }
        )
        group_c.refresh_from_db()
        self.assertEqual(group_c.priority_index, 100)
        group_b = ReportGroup.objects.get(id=group_b_id)
        self.assertEqual(group_b.priority_index, 0)

        # === 删除 ===
        DeletePanel().request({"id": p1["id"]})
        panels_after = ListManagePanels().request({})
        self.assertFalse(any(p["id"] == p1["id"] for p in panels_after))
        self.assertTrue(ReportGroup.objects.filter(id=group_b_id).exists())

        DeletePanel().request({"id": p2["id"]})
        self.assertFalse(ReportGroup.objects.filter(id=group_b_id).exists())

    @patch("services.web.vision.resources.panel.get_request_username", return_value="e2e_user")
    def test_preference_and_favorite_flow(self, _):
        # === 偏好 ===
        pref = GetPanelPreference().request({})
        self.assertEqual(pref, {"config": {}})

        UpdatePanelPreference().request({"config": {"collapsed": [1], "view": "grid"}})
        pref2 = GetPanelPreference().request({})
        self.assertEqual(pref2["config"], {"collapsed": [1], "view": "grid"})

        # === 收藏 ===
        group = ReportGroup.objects.create(name="收藏E2E分组", priority_index=0)
        panel = VisionPanel.objects.create(
            id="e2e_fav_p",
            name="E2E",
            group=group,
            scenario=Scenario.DEFAULT,
            is_enabled=True,
        )

        fav_resp = TogglePanelFavorite().request({"panel_id": panel.id, "is_favorite": True})
        self._assert_dict_contains(fav_resp, {"is_favorite": True})
        self.assertIsNotNone(fav_resp["favorite_at"])

        fav_resp2 = TogglePanelFavorite().request({"panel_id": panel.id, "is_favorite": True})
        self.assertTrue(fav_resp2["is_favorite"])
        self.assertEqual(UserPanelFavorite.objects.filter(username="e2e_user", panel=panel).count(), 1)

        unfav = TogglePanelFavorite().request({"panel_id": panel.id, "is_favorite": False})
        self._assert_dict_contains(unfav, {"is_favorite": False, "favorite_at": None})
        self.assertFalse(UserPanelFavorite.objects.filter(username="e2e_user", panel=panel).exists())
