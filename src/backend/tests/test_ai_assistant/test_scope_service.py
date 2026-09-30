from unittest import TestCase
from unittest.mock import Mock

from apps.permission.handlers.actions.action import ActionEnum
from core.exceptions import ValidationError
from services.web.ai_assistant.services.scope import (
    normalize_concrete_scope,
    resolve_scope_visibility,
)
from services.web.common.constants import ScopeType


class ScopePrimitivesTest(TestCase):
    def test_normalize_concrete_scope_canonicalizes_scene_id(self):
        scope = normalize_concrete_scope(scope_type="scene", scope_id="01")

        self.assertEqual((scope.scope_type, scope.scope_id), (ScopeType.SCENE, "1"))

    def test_normalize_concrete_scope_rejects_blank_system_id(self):
        with self.assertRaises(ValidationError):
            normalize_concrete_scope(scope_type="system", scope_id="  ")

    def test_normalize_concrete_rejects_invalid_and_cross_scope(self):
        for scope_type, scope_id in (
            ("scene", "invalid"),
            ("scene", None),
            ("system", ""),
            ("cross_scene", None),
            ("cross_system", None),
            ("unknown", "1"),
        ):
            with self.subTest(scope_type=scope_type, scope_id=scope_id):
                with self.assertRaises(ValidationError):
                    normalize_concrete_scope(scope_type=scope_type, scope_id=scope_id)

    def test_visibility_uses_shared_permission_and_matching_action(self):
        permission = Mock()
        permission.get_scene_ids.return_value = [1, 2]
        permission.get_system_ids.return_value = ["bk_audit"]
        scenes = resolve_scope_visibility(permission=permission, scope_type="cross_scene", scope_id=None)
        system = resolve_scope_visibility(permission=permission, scope_type="system", scope_id="bk_audit")
        self.assertEqual((scenes.scope_type, scenes.scope_ids, scenes.is_cross), (ScopeType.SCENE, ("1", "2"), True))
        self.assertEqual(
            (system.scope_type, system.scope_ids, system.is_cross), (ScopeType.SYSTEM, ("bk_audit",), False)
        )
        self.assertEqual(permission.get_scene_ids.call_args.args[1], ActionEnum.VIEW_SCENE)
        self.assertEqual(permission.get_system_ids.call_args.args[1], ActionEnum.VIEW_SYSTEM)
        permission.check_scope_entry.assert_not_called()

    def test_resolve_scope_visibility_does_not_check_cross_entry(self):
        permission = Mock()
        permission.get_scene_ids.return_value = []

        result = resolve_scope_visibility(permission=permission, scope_type="cross_scene", scope_id=None)

        self.assertEqual((result.scope_type, result.scope_ids, result.is_cross), (ScopeType.SCENE, (), True))
        permission.check_scope_entry.assert_not_called()

    def test_concrete_empty_visibility_does_not_authorize_entry(self):
        permission = Mock()
        permission.get_scene_ids.return_value = []
        result = resolve_scope_visibility(permission=permission, scope_type="scene", scope_id="01")
        self.assertEqual((result.scope_type, result.scope_ids, result.is_cross), (ScopeType.SCENE, (), False))
        permission.check_scope_entry.assert_not_called()
