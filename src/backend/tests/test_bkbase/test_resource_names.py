"""BKBase V4 资源名称构造的兼容约定。"""

from django.test import SimpleTestCase

from services.web.bkbase import common


class ResourceNameTests(SimpleTestCase):
    def test_stable_name_preserves_existing_format(self):
        cases = (
            (("flow", 313), "flow_313_8efbbe9bc19a"),
            (
                ("flow", "resource_name_" * 8),
                "flow_resource_name_resource_name_resource_nam_b0a3fef6771e",
            ),
            (
                ("s", "audit_iam_rtype_0123456789abcdef", "Doris", "clusters", "production", "default"),
                "s_audit_iam_rtype_0123456789abcdef_Doris_clus_1574c3c00563",
            ),
            (("c", "Snapshot", 271), "c_Snapshot_271_1aa61afb16a5"),
            (("tmp", "field.name/2", 7), "tmp_field_name_2_7_ffe03205bd22"),
        )

        for args, expected in cases:
            with self.subTest(args=args):
                self.assertEqual(common.stable_name(*args), expected)

    def test_build_resource_name_reserves_token_and_suffix(self):
        name = common.build_resource_name("x" * 100, "0123456789abcdef", max_length=60, suffix="_source")
        other = common.build_resource_name("x" * 100, "1123456789abcdef", max_length=60, suffix="_source")

        self.assertEqual(name, "x" * 36 + "_0123456789abcdef_source")
        self.assertNotEqual(name, other)

    def test_build_resource_name_normalizes_or_falls_back(self):
        self.assertEqual(
            common.build_resource_name("my app/01", "token", max_length=60),
            "my_app_01_token",
        )
        for readable in ("", "审计 / !", "!!!"):
            with self.subTest(readable=readable):
                self.assertEqual(common.build_resource_name(readable, "token", max_length=60), "resource_token")
        self.assertEqual(common.build_resource_name("-demo", "token", max_length=60), "_demo_token")
        self.assertEqual(common.build_resource_name("!!!", "a", max_length=4), "re_a")

    def test_build_resource_name_rejects_invalid_fixed_parts(self):
        invalid_calls = (
            lambda: common.build_resource_name("readable", "", max_length=60),
            lambda: common.build_resource_name("readable", "bad token", max_length=60),
            lambda: common.build_resource_name("readable", "token", max_length=60, suffix="_bad/"),
            lambda: common.build_resource_name("readable", "0123456789abcdef", max_length=16),
        )

        for call in invalid_calls:
            with self.subTest(call=call):
                with self.assertRaises(ValueError):
                    call()
