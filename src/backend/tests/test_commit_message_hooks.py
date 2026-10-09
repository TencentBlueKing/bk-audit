"""验证后端提交信息门禁的实际 Git 行为。

使用临时仓库和真实 pre-commit 入口，覆盖 tracker 漏检及前端范围隔离。
测试不连接业务数据库，不使用开发者的签名配置。
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT_RELATIVE = Path("agent/skills/generate-project-commit/scripts/commit_message.sh")
SCRIPT = BACKEND / SCRIPT_RELATIVE


class CommitMessageValidationTests(unittest.TestCase):
    """通过 shell 的输入和退出码验证标题契约。"""

    def validate(self, message, *options):
        """将 message 送入真实校验器，返回完整进程结果。"""
        return subprocess.run(["sh", str(SCRIPT), "validate", *options], input=message, text=True, capture_output=True)

    def test_subject_without_body_is_allowed(self):
        """合法标题不应因缺少可选正文被阻止。"""
        result = self.validate("refactor: 合并工作进程 --story=1001\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_tracker_cannot_be_hidden_in_body(self):
        """需求号必须位于标题末尾，正文不能替代标题关联。"""
        for message in (
            "fix: 修复检索\n\n- --story=1001\n",
            "fix: 修复检索 --story=abc\n",
            "fix: 修复检索 --story=1001 附加说明\n",
            "unknown: 修复检索 --story=1001\n",
            "fix:  --story=1001\n",
            "\nfix: 修复检索 --story=1001\n",
            "",
        ):
            with self.subTest(message=message):
                result = self.validate(message)
                self.assertEqual(result.returncode, 1, result.stderr)

    def test_supported_trackers_and_crlf(self):
        """GitHub、TAPD 与 CRLF message 均可使用。"""
        for message in ("fix: 修复检索 #1001\n", "fix: 修复检索 --bug=1001\r\n", "docs: 补充说明 --task=1001\n"):
            with self.subTest(message=message):
                result = self.validate(message)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_merge_requires_explicit_permission_for_manual_validation(self):
        """普通生成校验不能把合并标题作为普通提交使用。"""
        self.assertEqual(self.validate("Merge branch 'main'\n").returncode, 1)
        self.assertEqual(self.validate("Merge branch 'main'\n", "--allow-merge").returncode, 0)
        self.assertEqual(self.validate("MergeOops\n", "--allow-merge").returncode, 1)

    def test_missing_message_file_fails(self):
        """读取失败不能作为有效空输入放行。"""
        result = subprocess.run(
            ["sh", str(SCRIPT), "validate", "--message-file", "/nonexistent/commit-message"], capture_output=True
        )
        self.assertNotEqual(result.returncode, 0)


class BackendCommitHookTests(unittest.TestCase):
    """安装真实 commit-msg hook 后验证后端与前端提交范围。"""

    def setUp(self):
        """建立独立仓库和缓存，安装仅包含本次 local hook 的配置。"""
        self.temporary = tempfile.TemporaryDirectory(prefix="bk-audit-hook-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.env = dict(os.environ, PRE_COMMIT_HOME=str(Path(self.temporary.name) / "cache"))
        for variable in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"):
            self.env.pop(variable, None)
        self.git("init", "-q")
        self.git("config", "user.name", "Test Developer")
        self.git("config", "user.email", "developer@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        target = self.root / "src/backend" / SCRIPT_RELATIVE
        target.parent.mkdir(parents=True)
        if SCRIPT.exists():
            shutil.copyfile(SCRIPT, target)
        config = yaml.safe_load((BACKEND / ".pre-commit-config.yaml").read_text())
        config["repos"] = [repo for repo in config["repos"] if repo["repo"] == "local"]
        config_path = self.root / "src/backend/.pre-commit-config.yaml"
        config_path.write_text(yaml.safe_dump(config))
        self.git("add", "src/backend")
        self.git("commit", "-qm", "chore: 初始化工具测试 #1001")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pre_commit",
                "install",
                "--config=src/backend/.pre-commit-config.yaml",
                "--hook-type=commit-msg",
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def git(self, *arguments, check=True, cwd=None):
        """运行临时仓库的真实 Git 命令，不影响开发仓库。"""
        return subprocess.run(
            ["git", *arguments], cwd=cwd or self.root, env=self.env, capture_output=True, text=True, check=check
        )

    def stage_file(self, relative, cwd=None):
        """创建并暂存测试文件，支持同仓库的独立 worktree。"""
        root = cwd or self.root
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test content\n")
        self.git("add", relative, cwd=root)

    def test_missing_tracker_blocks_backend_commit_and_preserves_index(self):
        """后端漏写需求号时，不创建提交且保留原暂存内容。"""
        self.stage_file("src/backend/example.txt")
        result = self.git("commit", "-m", "fix: 修复检索", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout.strip(), "1")
        self.assertIn("src/backend/example.txt", self.git("diff", "--cached", "--name-only").stdout)

    def test_valid_backend_subject_creates_commit(self):
        """合法标题无需强制补正文即可提交后端改动。"""
        self.stage_file("src/backend/example.txt")
        result = self.git("commit", "-m", "fix: 修复检索 --story=1001", check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_frontend_only_commit_does_not_gain_backend_restrictions(self):
        """后端接入不能改变纯前端提交的标题要求。"""
        self.stage_file("src/frontend/example.txt")
        result = self.git("commit", "-m", "frontend change", check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_mixed_commit_still_requires_tracker(self):
        """混合提交含有后端改动时不能通过前端范围绕过。"""
        self.stage_file("src/backend/example.txt")
        self.stage_file("src/frontend/example.txt")
        self.assertNotEqual(self.git("commit", "-m", "fix: 修复检索", check=False).returncode, 0)

    def test_amend_without_staged_changes_is_checked(self):
        """无暂存差异的 message 改写仍需要校验标题。"""
        result = self.git("commit", "--amend", "-m", "fix: 修改标题", check=False)
        self.assertNotEqual(result.returncode, 0)

    def test_history_range_detects_invalid_earlier_commit(self):
        """历史范围检查必须发现较早的坏标题，不能只检查最新提交。"""
        base = self.git("rev-parse", "HEAD").stdout.strip()
        self.stage_file("src/frontend/first.txt")
        self.git("commit", "-qm", "frontend change")
        self.stage_file("src/frontend/second.txt")
        self.git("commit", "-qm", "fix: 更新界面 #1001")
        script = self.root / "src/backend" / SCRIPT_RELATIVE
        result = subprocess.run(
            ["sh", str(script), "check-range", f"{base}..HEAD"],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_history_invalid_revision_fails(self):
        """Git 无法读取历史时不能被管道掩盖为校验成功。"""
        script = self.root / "src/backend" / SCRIPT_RELATIVE
        result = subprocess.run(
            ["sh", str(script), "check-range", "missing-base..HEAD"],
            cwd=self.root,
            env=self.env,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_shared_hook_works_in_linked_worktree(self):
        """共享 Git hook 应读取当前 worktree 的后端配置和暂存区。"""
        worktree = Path(self.temporary.name) / "linked"
        self.git("worktree", "add", "-qb", "linked", str(worktree))
        self.stage_file("src/backend/example.txt", cwd=worktree)
        result = self.git("commit", "-m", "fix: 修复检索", check=False, cwd=worktree)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
