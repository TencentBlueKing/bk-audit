# -*- coding: utf-8 -*-
import datetime
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from services.web.risk.resources.whitelist import RiskWhitelistCallback
from services.web.risk.whitelist.constants import (
    HitAction,
    WhitelistStatus,
    WhitelistType,
)
from services.web.risk.whitelist.models import RiskWhitelist
from services.web.risk.whitelist.service import (
    _node_payload,
    create_itsm_ticket,
    expire_at_from,
    flow_of,
    intercept_whitelist,
    progress_map,
    resolve_duration,
    resolve_expire_at,
    submit_whitelist,
    validity_text,
)
from services.web.scene.constants import ITSMV4TicketStatus


def _scope():
    return {
        "connector": "and",
        "conditions": [
            {
                "condition": {
                    "field": {
                        "table": "event",
                        "raw_name": "operator",
                        "display_name": "operator",
                        "field_type": "string",
                    },
                    "operator": "eq",
                    "filter": "alice",
                }
            }
        ],
    }


class WhitelistCreateTests(SimpleTestCase):
    @patch("services.web.risk.whitelist.service.create_itsm_ticket")
    @patch("services.web.risk.whitelist.service.write_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.create")
    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    def test_single_risk_stores_token_and_eq_fields(self, scene_filter, create, write_nodes, create_ticket):
        scene_filter.return_value.exists.return_value = True
        created = {}

        def _create(**kwargs):
            created.update(kwargs)
            rule = SimpleNamespace(id=1, **kwargs)
            rule.refresh_from_db = lambda: None
            return rule

        create.side_effect = _create
        risk = SimpleNamespace(strategy_id=9, raw_event_id="evt-1", risk_id="risk-1", scene_id=1, current_operator=[])
        submit_whitelist(
            scene_id=1,
            match_scope=_scope(),
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            reason="接受一段时间",
            duration_days=15,
            risks=[risk],
            username="alice",
        )
        self.assertEqual(len(created["callback_token"]), 32)
        fields = {
            item["condition"]["field"]["raw_name"]: item["condition"] for item in created["match_scope"]["conditions"]
        }
        self.assertEqual(fields["strategy_id"]["operator"], "eq")
        self.assertEqual(fields["strategy_id"]["filter"], "9")
        self.assertEqual(fields["raw_event_id"]["operator"], "eq")
        self.assertEqual(fields["raw_event_id"]["filter"], "evt-1")
        self.assertNotIn("risk_id", fields)
        write_nodes.assert_called_once()
        create_ticket.assert_called_once_with(1)

    @patch("services.web.risk.whitelist.service.create_itsm_ticket")
    @patch("services.web.risk.whitelist.service.write_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.create")
    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    def test_batch_creates_one_rule_per_risk(self, scene_filter, create, write_nodes, create_ticket):
        scene_filter.return_value.exists.return_value = True
        created = []

        def _create(**kwargs):
            created.append(kwargs)
            rule = SimpleNamespace(id=len(created), **kwargs)
            rule.refresh_from_db = lambda: None
            return rule

        create.side_effect = _create
        risks = [
            SimpleNamespace(strategy_id=9, raw_event_id="evt-1", risk_id="risk-1", scene_id=3, current_operator=[]),
            SimpleNamespace(strategy_id=9, raw_event_id="evt-2", risk_id="risk-2", scene_id=3, current_operator=[]),
        ]
        rules = submit_whitelist(
            scene_id=3,
            match_scope=_scope(),
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            reason="批量接受",
            duration_days=15,
            risks=risks,
            username="alice",
        )
        self.assertEqual(len(rules), 2)
        self.assertEqual([item["risk_id"] for item in created], ["risk-1", "risk-2"])
        first_fields = {
            item["condition"]["field"]["raw_name"]: item["condition"]["filter"]
            for item in created[0]["match_scope"]["conditions"]
        }
        second_fields = {
            item["condition"]["field"]["raw_name"]: item["condition"]["filter"]
            for item in created[1]["match_scope"]["conditions"]
        }
        self.assertEqual(first_fields["strategy_id"], "9")
        self.assertEqual(second_fields["strategy_id"], "9")
        self.assertEqual(first_fields["raw_event_id"], "evt-1")
        self.assertEqual(second_fields["raw_event_id"], "evt-2")
        self.assertNotIn("risk_id", first_fields)
        self.assertNotIn("risk_id", second_fields)
        self.assertEqual(write_nodes.call_count, 2)
        self.assertEqual(create_ticket.call_count, 2)


class WhitelistTicketCreateTests(SimpleTestCase):
    @patch("services.web.risk.whitelist.service._abort_whitelist")
    @patch("services.web.risk.whitelist.service.RISK_WHITELIST_WORKFLOW_KEY", "workflow-key")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_create", side_effect=RuntimeError("boom"))
    @patch("services.web.risk.whitelist.service.RiskWhitelist.objects.filter")
    def test_ticket_create_failure_raises(self, query, ticket_create, abort):
        rule = SimpleNamespace(
            id=1,
            itsm_ticket_id="",
            created_by="alice",
            scene_id=1,
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            reason="接受一段时间",
            match_scope=_scope(),
            risk_id="risk-1",
            callback_token="token",
        )
        query.return_value.first.return_value = rule
        with self.assertRaises(ValidationError):
            create_itsm_ticket(1)
        abort.assert_called_once_with(rule)

    def test_batch_requires_same_strategy_and_scene(self):
        risks = [
            SimpleNamespace(strategy_id=9, raw_event_id="evt-1", risk_id="risk-1", scene_id=3),
            SimpleNamespace(strategy_id=8, raw_event_id="evt-2", risk_id="risk-2", scene_id=3),
        ]
        with self.assertRaises(ValidationError):
            submit_whitelist(
                scene_id=3,
                match_scope=_scope(),
                whitelist_type=WhitelistType.RISK_ACCEPTANCE,
                reason="批量接受",
                duration_days=15,
                risks=risks,
                username="alice",
            )


class WhitelistCallbackTests(SimpleTestCase):
    def _rule(self):
        return SimpleNamespace(
            callback_token="stored-token",
            status=WhitelistStatus.PENDING,
            itsm_ticket_id="ticket-1",
        )

    @patch("services.web.risk.resources.whitelist.apply_whitelist_result")
    @patch("services.web.risk.resources.whitelist.RiskWhitelist.objects.filter")
    def test_callback_rejects_unknown_token(self, query, apply_result):
        query.return_value.first.return_value = self._rule()
        result = RiskWhitelistCallback().perform_request(
            {
                "callback_token": "wrong",
                "ticket": {"id": "ticket-1", "status": "finished", "approve_result": True},
            }
        )
        self.assertFalse(result["result"])
        apply_result.assert_not_called()

    @patch("services.web.risk.resources.whitelist.apply_whitelist_result")
    @patch("services.web.risk.resources.whitelist.RiskWhitelist.objects.filter")
    def test_callback_with_stored_token_applies_ticket(self, query, apply_result):
        rule = self._rule()
        query.return_value.first.return_value = rule
        result = RiskWhitelistCallback().perform_request(
            {
                "callback_token": "stored-token",
                "ticket": {
                    "id": "ticket-1",
                    "status": ITSMV4TicketStatus.FINISHED,
                    "approve_result": True,
                    "comment": "",
                },
            }
        )
        self.assertTrue(result["result"])
        apply_result.assert_called_once_with(
            rule,
            {"id": "ticket-1", "status": ITSMV4TicketStatus.FINISHED, "approve_result": True, "comment": ""},
        )


class WhitelistDurationTests(SimpleTestCase):
    def test_defaults_and_custom_days(self):
        self.assertEqual(resolve_duration(WhitelistType.FALSE_POSITIVE), (True, None))
        self.assertEqual(resolve_duration(WhitelistType.RISK_ACCEPTANCE), (False, 30))
        self.assertEqual(resolve_duration(WhitelistType.RISK_ACCEPTANCE, duration_days=45), (False, 45))
        base = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        self.assertIsNone(expire_at_from(True, None, base))
        self.assertEqual(expire_at_from(False, 15, base), base + datetime.timedelta(days=15))
        fractional = datetime.datetime(2026, 12, 11, 8, 33, 41, 289366, tzinfo=datetime.timezone.utc)
        self.assertEqual(expire_at_from(False, 0, fractional), fractional.replace(microsecond=0))
        rule = SimpleNamespace(is_permanent=False, expire_at=fractional)
        self.assertEqual(validity_text(rule), "2026-12-11 16:33:41")

    def test_node_keeps_ticket_after_approve(self):
        expire = datetime.datetime(2026, 12, 11, 8, 33, 41, 289366, tzinfo=datetime.timezone.utc)
        rule = SimpleNamespace(
            id=1,
            is_permanent=False,
            expire_at=expire,
            match_scope={},
            created_by="admin",
            whitelist_type=WhitelistType.RISK_ACCEPTANCE,
            reason="接受",
            created_at=expire,
            itsm_ticket_id="102026111108334100059701",
            itsm_sn="DE2026111100000001",
            itsm_ticket_url="http://itsm/1",
        )
        payload = _node_payload(
            rule,
            {
                "status": ITSMV4TicketStatus.FINISHED,
                "approve_result": True,
                "current_processors": [{"processor": "admin"}],
                "current_steps": [{"name": "审批"}],
            },
        )
        self.assertEqual(payload["validity_text"], "2026-12-11 16:33:41")
        self.assertEqual(payload["itsm_ticket_id"], "102026111108334100059701")
        self.assertEqual(payload["itsm_sn"], "DE2026111100000001")
        self.assertEqual(payload["itsm_status"], WhitelistStatus.ACTIVE)
        self.assertEqual(payload["itsm_status_display"], "生效中")
        rule.status = WhitelistStatus.PENDING
        rule.itsm_ticket_url = "http://itsm/1"
        rule.updated_by = ""
        rule.reject_reason = ""
        rule.updated_at = None
        flow = flow_of(
            rule,
            {"current_processors": payload["current_processors"], "current_steps": payload["current_steps"]},
        )
        self.assertEqual(flow["itsm_sn"], "DE2026111100000001")
        self.assertEqual(flow["current_processors"], [{"processor": "admin"}])
        self.assertEqual(flow["current_steps"], [{"name": "审批"}])

    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_detail")
    def test_list_echoes_itsm_ticket(self, ticket_detail):
        ticket_detail.return_value = {
            "id": "102026111108334100059701",
            "sn": "DE2026111100000001",
            "frontend_url": "http://itsm/1",
            "status": "running",
            "status_display": "审批中",
            "approve_result": None,
            "current_processors": [],
            "current_steps": [{"name": "审批"}],
        }
        rule = SimpleNamespace(
            id=1,
            status=WhitelistStatus.PENDING,
            itsm_ticket_id="102026111108334100059701",
            itsm_sn="",
            itsm_ticket_url="",
            updated_by="",
            reject_reason="",
            updated_at=None,
        )
        echoed = progress_map([rule])["1"]
        flow = flow_of(rule, echoed)
        ticket_detail.assert_called_once_with(id="102026111108334100059701")
        self.assertEqual(flow["itsm_sn"], "DE2026111100000001")
        self.assertEqual(flow["itsm_url"], "http://itsm/1")
        self.assertEqual(flow["status"], WhitelistStatus.PENDING)
        self.assertEqual(flow["status_display"], "待审批")
        self.assertEqual(flow["current_processors"], [])
        self.assertEqual(flow["current_steps"], [{"name": "审批"}])

    def test_custom_time_is_the_expire_at(self):
        from django.utils import timezone

        text = "2026-12-31 18:00:00"
        permanent, expire_at = resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="custom", expire_at=text)
        self.assertFalse(permanent)
        self.assertEqual(timezone.localtime(expire_at).strftime("%Y-%m-%d %H:%M:%S"), text)
        with self.assertRaises(ValidationError):
            resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="custom")
        with self.assertRaises(ValidationError):
            resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="custom", expire_at="2020-01-01 00:00:00")

    def test_one_month_uses_a_calendar_month(self):
        base = datetime.datetime(2026, 1, 31, 8, 33, 41, tzinfo=datetime.timezone.utc)
        permanent, expire_at = resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="1m", base=base)
        self.assertFalse(permanent)
        self.assertEqual(expire_at, datetime.datetime(2026, 2, 28, 8, 33, 41, tzinfo=datetime.timezone.utc))
        _, mid_month = resolve_expire_at(
            WhitelistType.RISK_ACCEPTANCE,
            duration_days="1M",
            base=datetime.datetime(2026, 3, 15, 10, 0, 0, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(mid_month, datetime.datetime(2026, 4, 15, 10, 0, 0, tzinfo=datetime.timezone.utc))

    def test_permanent_duration(self):
        permanent, expire_at = resolve_expire_at(WhitelistType.FALSE_POSITIVE, duration_days="permanent")
        self.assertTrue(permanent)
        self.assertIsNone(expire_at)
        with self.assertRaises(ValidationError):
            resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="permanent")

    def test_risk_acceptance_cannot_be_permanent(self):
        with self.assertRaises(ValidationError):
            resolve_expire_at(WhitelistType.RISK_ACCEPTANCE, duration_days="permanent")


class _Rule:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.id = 1
        self.pk = 1
        self.itsm_ticket_id = ""
        self.itsm_sn = ""
        self.itsm_ticket_url = ""
        self.expire_at = kwargs.get("expire_at")
        self.reject_reason = ""
        self.updated_at = None
        self.created_at = None

    def save(self, update_fields=None):
        return None

    def refresh_from_db(self):
        return None


class _WhitelistQuery:
    def __init__(self, rules, kwargs):
        self.rules = rules
        self.kwargs = kwargs

    def _matched(self):
        matched = []
        for rule in self.rules:
            if "pk" in self.kwargs and self.kwargs["pk"] != rule.id:
                continue
            if "itsm_ticket_id" in self.kwargs and self.kwargs["itsm_ticket_id"] != rule.itsm_ticket_id:
                continue
            if "status" in self.kwargs and self.kwargs["status"] != rule.status:
                continue
            if "scene_id" in self.kwargs and self.kwargs["scene_id"] != rule.scene_id:
                continue
            matched.append(rule)
        return matched

    def first(self):
        matched = self._matched()
        return matched[0] if matched else None

    def only(self, *fields):
        return self

    def __iter__(self):
        return iter(self._matched())


class _WhitelistManager:
    def __init__(self):
        self.rules = []

    def create(self, **kwargs):
        rule = _Rule(**kwargs)
        self.rules.append(rule)
        return rule

    def filter(self, **kwargs):
        return _WhitelistQuery(self.rules, kwargs)

    def select_for_update(self):
        return self

    def get(self, pk):
        return next(rule for rule in self.rules if rule.pk == pk)


@contextmanager
def _noop_atomic():
    yield


class WhitelistFlowTests(SimpleTestCase):
    @patch("services.web.risk.whitelist.service.refresh_whitelist_nodes")
    @patch("services.web.risk.whitelist.service._find_converged_risk", return_value=None)
    @patch("services.web.risk.whitelist.service.RiskWhitelistHit.objects.bulk_create")
    @patch("services.web.risk.whitelist.service.is_scene_admin", return_value=False)
    @patch("services.web.risk.whitelist.service.RISK_WHITELIST_WORKFLOW_KEY", "workflow-key")
    @patch("services.web.risk.whitelist.service.api.bk_itsm_v4.ticket_create")
    @patch("services.web.risk.whitelist.service.transaction.atomic", _noop_atomic)
    @patch("services.web.risk.whitelist.service.write_whitelist_nodes")
    @patch("services.web.risk.whitelist.service.Scene.objects.filter")
    def test_create_callback_then_intercept(
        self,
        scene_filter,
        write_nodes,
        ticket_create,
        is_admin,
        bulk_create,
        find_risk,
        refresh_nodes,
    ):
        manager = _WhitelistManager()
        scene_filter.return_value.exists.return_value = True

        def _ticket_create(**kwargs):
            rule = manager.rules[0]
            self.assertEqual(kwargs["callback_token"], rule.callback_token)
            self.assertIn("/risk_whitelist_callback/callback/", kwargs["callback_url"])
            return {
                "id": "ticket-1",
                "sn": "SN1",
                "frontend_url": "http://itsm/ticket-1",
                "status": "running",
            }

        ticket_create.side_effect = _ticket_create
        risk = SimpleNamespace(strategy_id=9, raw_event_id="evt-1", risk_id="risk-1", scene_id=3, current_operator=[])
        with patch.object(RiskWhitelist, "objects", manager):
            rule = submit_whitelist(
                scene_id=3,
                match_scope=_scope(),
                whitelist_type=WhitelistType.RISK_ACCEPTANCE,
                reason="接受一段时间",
                duration_days=15,
                risks=[risk],
                username="alice",
            )
            self.assertEqual(rule.status, WhitelistStatus.PENDING)
            self.assertEqual(rule.itsm_ticket_id, "ticket-1")
            self.assertEqual(rule.itsm_sn, "SN1")
            self.assertEqual(rule.itsm_ticket_url, "http://itsm/ticket-1")
            with patch("services.web.risk.whitelist.service._close_source_risk"):
                result = RiskWhitelistCallback().perform_request(
                    {
                        "callback_token": rule.callback_token,
                        "ticket": {
                            "id": "ticket-1",
                            "status": ITSMV4TicketStatus.FINISHED,
                            "approve_result": True,
                            "comment": "",
                        },
                    }
                )
            self.assertTrue(result["result"])
            self.assertEqual(rule.status, WhitelistStatus.ACTIVE)
            self.assertIsNotNone(rule.expire_at)
            event = {
                "strategy_id": "9",
                "raw_event_id": "evt-1",
                "risk_id": "risk-1",
                "operator": "alice",
            }
            self.assertTrue(intercept_whitelist(event, {}, 3))
            hit = bulk_create.call_args.args[0][0]
            self.assertEqual(hit.action, HitAction.SUPPRESS_NEW)
            self.assertEqual(hit.risk_id, "")
            self.assertFalse(intercept_whitelist({**event, "operator": "bob"}, {}, 3))
