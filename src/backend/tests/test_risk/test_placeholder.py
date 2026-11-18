"""placeholder 模块单元测试"""

from services.web.risk.placeholder import (
    PersonnelRef,
    normalize_personnel_refs,
    render_payload,
    render_string,
    resolve_personnel_refs,
)
from tests.base import TestCase as BaseTestCase


class _StubRisk:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestRenderString(BaseTestCase):
    def test_plain_string_unchanged(self):
        self.assertEqual(render_string("hello"), "hello")

    def test_operator_placeholder(self):
        self.assertEqual(render_string("by {{operator}}", operator="alice"), "by alice")

    def test_field_placeholder(self):
        risk = _StubRisk(risk_id="r-1", operator=["u1", "u2"])
        self.assertEqual(render_string("id={{risk_id}}", risk=risk), "id=r-1")
        # 保留字：{{operator}} 始终代表当前操作用户，不会解析成 risk.operator 列表
        self.assertEqual(render_string("op={{operator}}", risk=risk, operator="alice"), "op=alice")

    def test_event_data_dot_path(self):
        risk = _StubRisk(event_data={"a": {"b": "v"}})
        self.assertEqual(render_string("{{event_data.a.b}}", risk=risk), "v")

    def test_missing_field_becomes_empty(self):
        risk = _StubRisk(event_data={})
        self.assertEqual(render_string("{{event_data.miss.path}}", risk=risk), "")

    def test_allow_event_data_false(self):
        risk = _StubRisk(event_data={"a": "v"})
        self.assertEqual(render_string("{{event_data.a}}", risk=risk, allow_event_data=False), "")


class TestRenderPayload(BaseTestCase):
    def test_field_mapping_passthrough(self):
        payload = {"c1": {"value": "{{operator}}", "field": "operator"}}
        out = render_payload(payload, risk=_StubRisk(operator=["u1"]), operator="alice")
        # 字段映射路径：value 原样透传，交给 AutoProcess 处理
        self.assertEqual(out["c1"]["value"], "{{operator}}")

    def test_direct_value_rendered(self):
        payload = {"c1": {"value": "hello {{operator}}", "field": ""}}
        out = render_payload(payload, risk=None, operator="bob")
        self.assertEqual(out["c1"]["value"], "hello bob")


class TestPersonnelRefs(BaseTestCase):
    def test_backward_compat_str(self):
        refs = normalize_personnel_refs(["alice", "bob"])
        self.assertEqual([r.type for r in refs], [PersonnelRef.USER, PersonnelRef.USER])
        self.assertEqual([r.value for r in refs], ["alice", "bob"])

    def test_dict_ref(self):
        refs = normalize_personnel_refs([{"type": "field", "value": "operator"}])
        self.assertEqual(refs[0].type, "field")

    def test_resolve_user_refs(self):
        out = resolve_personnel_refs([{"type": "user", "value": "alice"}], risk=None)
        self.assertEqual(out, ["alice"])

    def test_resolve_field_ref_list(self):
        risk = _StubRisk(operator=["u1", "u2"], current_operator=[])
        out = resolve_personnel_refs([{"type": "field", "value": "operator"}], risk=risk)
        self.assertEqual(out, ["u1", "u2"])

    def test_dedup(self):
        risk = _StubRisk(operator=["u1"], current_operator=[])
        out = resolve_personnel_refs(
            [
                {"type": "user", "value": "u1"},
                {"type": "field", "value": "operator"},
            ],
            risk=risk,
        )
        self.assertEqual(out, ["u1"])

    def test_event_data_denied(self):
        risk = _StubRisk(event_data={"owner": "zoe"})
        out = resolve_personnel_refs(
            [{"type": "field", "value": "event_data.owner"}],
            risk=risk,
            allow_event_data=False,
        )
        self.assertEqual(out, [])
