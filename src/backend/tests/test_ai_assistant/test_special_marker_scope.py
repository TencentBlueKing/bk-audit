from pathlib import Path

from django.test import SimpleTestCase

from tests.test_ai_assistant.special.conftest import pytest_collection_modifyitems


class _FakeItem:
    """只实现 collection hook 所需的最小 pytest Item 接口。"""

    def __init__(self, path: Path):
        self.path = path
        self.markers = []

    def get_closest_marker(self, _name):
        return None

    def add_marker(self, marker):
        self.markers.append(marker)


class SpecialMarkerScopeTest(SimpleTestCase):
    def test_collection_hook_does_not_mark_regular_test(self):
        item = _FakeItem(Path(__file__))

        pytest_collection_modifyitems([item])

        self.assertEqual(item.markers, [])
