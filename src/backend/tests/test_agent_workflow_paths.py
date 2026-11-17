"""静态检查后端质量工作流的触发范围与 required check 契约，不调用 GitHub 或业务服务。"""

import unittest
from pathlib import Path

import yaml

REPOSITORY = Path(__file__).resolve().parents[3]
WORKFLOW = REPOSITORY / ".github/workflows/pre-commit.yml"


def matches_paths(path: str, patterns: list[str]) -> bool:
    """匹配本工作流的字面路径和目录 /** 并集；遇到其他 glob 时抛出 ValueError。"""
    matched = False
    for pattern in patterns:
        if pattern.endswith("/**") and not any(char in pattern[:-3] for char in "*?[]!"):
            matched |= path.startswith(pattern[:-2])
        elif not any(char in pattern for char in "*?[]!"):
            matched |= path == pattern
        else:
            raise ValueError(f"Unsupported workflow path pattern: {pattern}")
    return matched


class AgentWorkflowPathTests(unittest.TestCase):
    """读取实际 YAML；PR 始终上报，push 保留路径过滤，后端重步骤按检测结果执行。"""

    @classmethod
    def setUpClass(cls):
        """以纯标量加载器读取配置，保留 on 键，不解释布尔值或执行自定义标签。"""
        cls.workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
        cls.events = cls.workflow["on"]
        cls.job = cls.workflow["jobs"]["pre-commit"]

    def test_pull_requests_always_report_required_check(self):
        """不能按 PR 路径或整个 job 的条件跳过 required check。"""
        self.assertNotIn("paths", self.events["pull_request"])
        self.assertNotIn("paths-ignore", self.events["pull_request"])
        self.assertEqual(self.job["name"], "Backend pre-commit")
        self.assertNotIn("if", self.job)
        self.assertNotIn("continue-on-error", self.job)

    def test_moved_backend_tool_paths_trigger_main_push(self):
        """迁移后的任一后端标题工具仍通过 main push 的 paths 过滤。"""
        for name in ("commit_message.sh", "commit_message.py"):
            path = f"agent/backend/tools/commit-message/{name}"
            with self.subTest(path=path):
                self.assertTrue((REPOSITORY / path).is_file())
                self.assertTrue(matches_paths(path, self.events["push"]["paths"]))

    def test_backend_and_ci_paths_trigger_main_push(self):
        """后端配置、工作流及路径检测脚本和测试的修改均触发质量检查。"""
        for path in (
            "src/backend/.pre-commit-config.yaml",
            ".github/workflows/pre-commit.yml",
            ".github/scripts/backend-pre-commit.cjs",
            ".github/scripts/backend-pre-commit.test.cjs",
        ):
            with self.subTest(path=path):
                self.assertTrue(matches_paths(path, self.events["push"]["paths"]))

    def test_unrelated_paths_do_not_expand_main_push_scope(self):
        """前端、shared 导航和根 README 不加入 main push 的后端路径范围。"""
        for path in (
            "src/frontend/package.json",
            "agent/frontend/README.md",
            "agent/shared/README.md",
            "readme_en.md",
        ):
            with self.subTest(path=path):
                self.assertFalse(matches_paths(path, self.events["push"]["paths"]))

    def test_detection_runs_before_conditional_backend_steps(self):
        """路径测试和检测不能被跳过或忽略失败，且必须先于后端环境安装。"""
        steps = self.job["steps"]
        tests = next(step for step in steps if step["name"] == "Test backend change detection")
        detection = next(step for step in steps if step.get("id") == "changes")
        self.assertEqual(tests["run"], "node --test .github/scripts/backend-pre-commit.test.cjs")
        self.assertIn("require('./.github/scripts/backend-pre-commit.cjs')", detection["with"]["script"])
        self.assertIn("return await needsBackendChecks({ github, context })", detection["with"]["script"])
        for step in (tests, detection):
            self.assertNotIn("if", step)
        for step in steps:
            self.assertNotIn("continue-on-error", step)
        self.assertLess(steps.index(tests), steps.index(detection))
        self.assertLess(
            steps.index(detection), next(i for i, step in enumerate(steps) if step["name"] == "Set up Python")
        )
        self.assertEqual(self.workflow["permissions"], {"contents": "read", "pull-requests": "read"})

    def test_all_backend_steps_require_positive_detection(self):
        """纯前端跳过重步骤；不能仅以检测未失败或输出非空作为执行条件。"""
        steps = {step["name"]: step for step in self.job["steps"]}
        for name in (
            "Set up Python",
            "Cache pre-commit environments",
            "Update OS certificates",
            "Bootstrap verified pip",
            "Install pre-commit",
            "Check all backend files",
        ):
            with self.subTest(step=name):
                self.assertEqual(steps[name]["if"], "steps.changes.outputs.result == 'true'")
        self.assertEqual(steps["Check all backend files"]["run"], "pre-commit run --all-files --show-diff-on-failure")
        self.assertEqual(steps["Report frontend-only skip"]["if"], "steps.changes.outputs.result == 'false'")

    def test_branch_filters_and_manual_trigger_are_preserved(self):
        """PR 保留原分支范围，push 只面向 main，手动入口仍存在。"""
        self.assertEqual(self.events["pull_request"]["branches"], ["**"])
        self.assertEqual(self.events["push"]["branches"], ["main"])
        self.assertIn("workflow_dispatch", self.events)


if __name__ == "__main__":
    unittest.main()
