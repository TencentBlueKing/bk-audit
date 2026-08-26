from pathlib import Path

import pytest

SPECIAL_TEST_ROOT = Path(__file__).parent


def pytest_collection_modifyitems(items):
    """special/ 目录默认打 special marker，避免漏标后进入常规门禁。"""

    marker = pytest.mark.special
    for item in items:
        if not Path(item.path).is_relative_to(SPECIAL_TEST_ROOT):
            continue
        if item.get_closest_marker("special") is None:
            item.add_marker(marker)
