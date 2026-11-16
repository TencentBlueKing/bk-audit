"""验证并发完整PUT在项目资源锁内读取最新状态。

上游仅提供完整覆盖写接口，两次更新必须串行GET/PUT。
锁繁忙调用可重试，不能静默丢失另一份已保存配置。
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from time import sleep
from unittest import mock

from django.test import SimpleTestCase

from core.exceptions import LockError
from services.web.bkbase import clean


class CleanLockingTests(SimpleTestCase):
    def test_concurrent_full_put_preserves_both_updates(self):
        context = {"tenant": "tenant_a", "namespace": "audit"}
        ref = {**context, "kind": "Clean", "name": "concurrent_clean_test"}
        remote = {
            "metadata": {"name": ref["name"]},
            "spec": {
                "rules": [],
                "description": "old",
                "config_revision": 1,
                "deploy_revision": 1,
                "desired_status": "Running",
                "current_status": "Running",
            },
            "status": {"phase": "Ok"},
        }
        start = Barrier(2)

        def get(**kwargs):
            snapshot = deepcopy(remote)
            sleep(0.02)
            return snapshot

        def put(**kwargs):
            remote["spec"] = deepcopy(kwargs["spec"])
            return deepcopy(remote)

        def update(patch):
            start.wait(timeout=5)
            for attempt in range(5):
                try:
                    return clean.update_clean(context, ref, patch=patch, publish=False)
                except LockError:
                    if attempt == 4:
                        raise
                    sleep(0.05)

        rules = [{"input_id": "__raw_data", "output_id": "json", "operator": {"type": "json_de"}}]
        with mock.patch("services.web.bkbase.clean.api.bk_base_v4.clean_get", side_effect=get), mock.patch(
            "services.web.bkbase.clean.api.bk_base_v4.clean_update", side_effect=put
        ), ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(update, patch) for patch in ({"rules": rules}, {"description": "new"})]
            for future in futures:
                future.result(timeout=10)
        self.assertEqual((remote["spec"]["rules"], remote["spec"]["description"]), (rules, "new"))
        self.assertEqual(remote["spec"]["deploy_revision"], 1)
