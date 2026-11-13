"""验证V4微信退出的选项、保存和存量发送边界，V3渠道保持可用。"""

import json
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import ValidationError

from apps.notice.handlers.base import NoticeHandler
from apps.notice.models import NoticeGroup
from apps.notice.resources import CreateNoticeGroup, GetMsgType, UpdateNoticeGroup
from apps.notice.serializers import NoticeConfigSerializer, NoticeGroupInfoSerializer


@override_settings(BKBASE_API_VERSION="v4", LANGUAGE_CODE="zh-hans")
class ChannelAvailabilityTests(SimpleTestCase):
    """控制外部发送与持久化边界，验证真实Resource和Handler行为。"""

    def available_types(self):
        rows = [
            {"type": value, "label": value, "icon": value + ".svg", "is_active": True}
            for value in ["weixin", "rtx", "mail", "voice", "sms"]
        ]
        rows.append({"type": "unrelated", "label": "unrelated", "icon": "unused", "is_active": True})
        with mock.patch("apps.notice.resources.api.bk_cmsi.get_msg_type", return_value={"data": rows}):
            return GetMsgType().request()

    def test_v4_options_keep_standard_channels_and_hide_weixin(self):
        self.assertEqual([row["id"] for row in self.available_types()], ["rtx", "mail", "voice", "sms"])

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_options_keep_weixin(self):
        self.assertEqual([row["id"] for row in self.available_types()], ["weixin", "rtx", "mail", "voice", "sms"])

    def test_create_and_update_reject_weixin_before_persistence(self):
        for resource, identity in [(CreateNoticeGroup(), {"scene_id": 7}), (UpdateNoticeGroup(), {"group_id": 7})]:
            for channels in [["weixin"], ["weixin", "mail"]]:
                with self.subTest(resource=type(resource).__name__, channels=channels), mock.patch.object(
                    resource, "perform_request", side_effect=AssertionError("Must reject before persistence")
                ):
                    with self.assertRaises(Exception) as caught:
                        resource.request(
                            **identity,
                            group_name="synthetic_notice",
                            group_member=["synthetic_user"],
                            notice_config=[{"msg_type": value} for value in channels],
                        )
                    self.assertIn("移除微信", str(caught.exception))

    def test_v4_standard_channels_remain_valid_for_writes(self):
        serializer = NoticeConfigSerializer(data=[{"msg_type": c} for c in ["rtx", "mail", "voice", "sms"]], many=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_keeps_weixin_write_contract(self):
        serializer = NoticeConfigSerializer(data={"msg_type": "weixin"})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_v4_nested_write_validation_rejects_weixin(self):
        serializer = NoticeConfigSerializer(data={"msg_type": "weixin"})
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_legacy_config_is_still_readable_without_rewriting_it(self):
        config = [{"msg_type": "weixin"}, {"msg_type": "mail"}]
        group = NoticeGroup(group_id=7, group_name="synthetic_notice", group_member=[], notice_config=config)
        self.assertEqual(NoticeGroupInfoSerializer(group).data["notice_config"], config)
        self.assertEqual(group.notice_config, config)

    def dispatch(self, channels):
        notice = SimpleNamespace(
            id=7,
            receivers=["synthetic_user"],
            msg_type=list(channels),
            title="old_title",
            content="old_content",
            save=mock.Mock(),
        )
        sent = []
        builder = mock.Mock()
        builder.build_msg.side_effect = lambda **kw: ("title", "content", None, {"channel": kw["msg_type"]})

        def sender(**kwargs):
            return SimpleNamespace(send=lambda: sent.append(kwargs["channel"]) or {"ok": True})

        with mock.patch("apps.notice.handlers.base.BUILDERS", {"risk": mock.Mock(return_value=builder)}), mock.patch(
            "apps.notice.handlers.base.SENDERS", {key: sender for key in ["weixin", "rtx", "mail"]}
        ):
            NoticeHandler(0, "risk", "", [notice])._send(notice, need_agg=False)
        self.assertEqual(notice.msg_type, channels)
        notice.save.assert_called_once()
        return notice, sent

    def test_v4_mixed_legacy_channels_send_supported_channels_and_record_weixin_failure(self):
        with mock.patch("apps.notice.handlers.base.logger.warning") as warning:
            notice, sent = self.dispatch(["weixin", "mail", "rtx"])
        self.assertEqual(sent, ["mail", "rtx"])
        self.assertTrue(notice.schedule_result)
        errors = [row["Error"] for row in json.loads(notice.debug_info) if "Error" in row]
        self.assertEqual(len(errors), 1)
        self.assertIn("移除微信", errors[0])
        warning.assert_called_once()

    def test_v4_only_weixin_fails_without_fallback_channel(self):
        notice, sent = self.dispatch(["weixin"])
        self.assertEqual(sent, [])
        self.assertFalse(notice.schedule_result)
        self.assertIn("移除微信", notice.debug_info)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_still_dispatches_weixin(self):
        notice, sent = self.dispatch(["weixin"])
        self.assertEqual(sent, ["weixin"])
        self.assertTrue(notice.schedule_result)
