"""静态检查后端 Agent 文件迁移后的质量工作流触发范围，不调用 GitHub 或业务服务。"""

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
    """读取实际 YAML，覆盖迁移路径、原触发路径、排除范围和现有分支限制。"""

    @classmethod
    def setUpClass(cls):
        """以纯标量加载器读取配置，保留 on 键，不解释布尔值或执行自定义标签。"""
        cls.events = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)["on"]

    def test_moved_backend_tool_paths_trigger_pr_and_main_push(self):
        """仅修改迁移后的任一后端标题工具，也应通过两个事件的 paths 过滤。"""
        for event in ("pull_request", "push"):
            for name in ("commit_message.sh", "commit_message.py"):
                path = f"agent/backend/tools/commit-message/{name}"
                with self.subTest(event=event, path=path):
                    self.assertTrue((REPOSITORY / path).is_file())
                    self.assertTrue(matches_paths(path, self.events[event]["paths"]))

    def test_existing_backend_and_workflow_paths_still_trigger(self):
        """原后端配置与工作流自修改继续触发质量检查。"""
        for event in ("pull_request", "push"):
            for path in ("src/backend/.pre-commit-config.yaml", ".github/workflows/pre-commit.yml"):
                with self.subTest(event=event, path=path):
                    self.assertTrue(matches_paths(path, self.events[event]["paths"]))

    def test_unrelated_paths_do_not_expand_backend_scope(self):
        """前端、shared 导航和根 README 不因本次修复加入后端路径范围。"""
        for event in ("pull_request", "push"):
            for path in (
                "src/frontend/package.json",
                "agent/frontend/README.md",
                "agent/shared/README.md",
                "readme_en.md",
            ):
                with self.subTest(event=event, path=path):
                    self.assertFalse(matches_paths(path, self.events[event]["paths"]))

    def test_branch_filters_and_manual_trigger_are_preserved(self):
        """PR 保留原分支范围，push 只面向 main，手动入口仍存在。"""
        self.assertEqual(self.events["pull_request"]["branches"], ["**"])
        self.assertEqual(self.events["push"]["branches"], ["main"])
        self.assertIn("workflow_dispatch", self.events)


if __name__ == "__main__":
    unittest.main()
