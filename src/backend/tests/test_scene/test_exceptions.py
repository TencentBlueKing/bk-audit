# -*- coding: utf-8 -*-
from django.test import SimpleTestCase

from services.web.scene.exceptions import (
    PanelCannotDelete,
    PanelNotExist,
    SceneDisabled,
    SceneHasRelatedResources,
    SceneNotExist,
    ToolCannotDelete,
    ToolNotExist,
)


class TestSceneExceptions(SimpleTestCase):
    def test_scene_exceptions_use_non_500_status_codes(self):
        cases = [
            (SceneNotExist, 404),
            (PanelNotExist, 404),
            (ToolNotExist, 404),
            (SceneDisabled, 400),
            (SceneHasRelatedResources, 400),
            (PanelCannotDelete, 400),
            (ToolCannotDelete, 400),
        ]
        for exception_cls, status_code in cases:
            with self.subTest(exception_cls=exception_cls.__name__):
                self.assertEqual(exception_cls.STATUS_CODE, status_code)
