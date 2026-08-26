import unittest

from django.test import SimpleTestCase

from tests.test_ai_assistant.risk_matrix import RISK_CASES


def _flatten_tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten_tests(item)
        else:
            yield item


class RiskMatrixIntegrityTest(SimpleTestCase):
    def test_risk_ids_are_unique(self):
        risk_ids = [case.risk_id for case in RISK_CASES]
        self.assertEqual(len(risk_ids), len(set(risk_ids)), risk_ids)

    def test_each_risk_case_points_to_exactly_one_loadable_test(self):
        loader = unittest.defaultTestLoader
        for case in RISK_CASES:
            self.assertIn(case.ci_suite, {"regular", "special"}, case.risk_id)
            suite = loader.loadTestsFromName(case.test_id)
            self.assertEqual(
                suite.countTestCases(),
                1,
                f"{case.risk_id} 无法加载唯一测试: {case.test_id}",
            )
            loaded = list(_flatten_tests(suite))
            self.assertEqual(len(loaded), 1, case.test_id)
            self.assertNotIn(
                "FailedTest",
                type(loaded[0]).__name__,
                f"{case.risk_id} 测试 ID 无法导入: {case.test_id}",
            )
            self.assertEqual(loaded[0].id(), case.test_id)

    def test_ci_suite_matches_test_module_boundary(self):
        for case in RISK_CASES:
            expected_suite = "special" if ".special." in case.test_id else "regular"
            self.assertEqual(
                case.ci_suite,
                expected_suite,
                f"{case.risk_id} 的 ci_suite 与测试模块不一致: {case.test_id}",
            )

    def test_production_stack_sse_risks_are_registered_as_special(self):
        expected = {
            "R34": "test_first_event_arrives_before_task_finishes",
            "R35": "test_last_event_id_resumes_without_replaying_consumed_event",
            "R36": "test_retry_resets_live_old_connection_and_new_stream_completes",
        }
        cases = {case.risk_id: case for case in RISK_CASES}

        self.assertEqual(set(expected) - set(cases), set())
        for risk_id, method_name in expected.items():
            case = cases[risk_id]
            self.assertEqual(case.ci_suite, "special")
            self.assertIn("tests.test_ai_assistant.special.test_sse_e2e.GunicornSSESpecialTest", case.test_id)
            self.assertTrue(case.test_id.endswith(method_name), case.test_id)
