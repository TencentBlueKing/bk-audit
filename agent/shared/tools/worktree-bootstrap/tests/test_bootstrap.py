"""Integration tests: only disposable local repositories, never the user's hooks."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bootstrap.py"
SHARE = "src/backend/debug/开发方案/task one"


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bootstrap test ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.repo = self.base / "source repo"
        self.repo.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for name in list(self.env):
            if name.startswith("GIT_") and name not in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM"):
                self.env.pop(name)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        for rel in ("AGENTS.md", "src/backend/AGENTS.md"):
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# Current checkout instructions\n")
        (self.repo / ".gitignore").write_text("debug/\n.agents/\n")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        (self.repo / SHARE).mkdir(parents=True)
        (self.repo / SHARE / "evidence.txt").write_text("keep")
        self.target = self.base / "target tree"
        self.git("worktree", "add", "--detach", str(self.target))

    def git(self, *args, cwd=None, ok=True):
        r = subprocess.run(["git", "-C", str(cwd or self.repo), *args], env=self.env, text=True, capture_output=True)
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def cli(self, command, *args, cwd=None, ok=True):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--worktree", str(cwd or self.target), command, *map(str, args)],
            env=self.env,
            text=True,
            capture_output=True,
        )
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def configure(self):
        self.cli("configure", "--source-root", self.repo, "--share", SHARE)

    def test_check_without_sharing_policy_still_checks_checkout(self):
        result = self.cli("check")
        self.assertIn("OK checkout instructions: AGENTS.md", result.stdout)
        self.assertIn("no material sharing policy", result.stdout)
        self.assertFalse((self.target / SHARE).exists())
        self.assertNotEqual(self.cli("apply", ok=False).returncode, 0)
        (self.target / "AGENTS.md").unlink()
        self.assertNotEqual(self.cli("check", ok=False).returncode, 0)

    def test_check_is_read_only_and_apply_is_idempotent(self):
        self.configure()
        r = self.cli("check", ok=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.target / "src/backend/debug").exists())
        self.cli("apply")
        link = self.target / SHARE
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), self.repo / SHARE)
        self.cli("apply")
        self.cli("check")
        self.assertFalse(self.git("status", "--porcelain", cwd=self.target).stdout)

    def test_preserves_existing_directory_and_wrong_or_broken_link(self):
        self.configure()
        p = self.target / SHARE
        p.mkdir(parents=True)
        (p / "mine").write_text("untouched")
        self.assertNotEqual(self.cli("apply", ok=False).returncode, 0)
        self.assertEqual((p / "mine").read_text(), "untouched")
        (p / "mine").unlink()
        p.rmdir()
        p.symlink_to(self.base / "does not exist")
        self.assertNotEqual(self.cli("apply", ok=False).returncode, 0)
        self.assertEqual(os.readlink(p), str(self.base / "does not exist"))

    def test_rejects_ancestor_link_without_writing_into_source(self):
        self.configure()
        parent = self.target / "src/backend/debug"
        parent.symlink_to(self.repo / "src/backend/debug", target_is_directory=True)
        self.assertNotEqual(self.cli("apply", ok=False).returncode, 0)
        self.assertEqual((self.repo / SHARE / "evidence.txt").read_text(), "keep")

    def test_missing_source_is_not_created(self):
        self.configure()
        (self.repo / SHARE / "evidence.txt").unlink()
        (self.repo / SHARE).rmdir()
        self.assertNotEqual(self.cli("apply", ok=False).returncode, 0)
        self.assertFalse((self.target / SHARE).exists())

    def test_rejects_unsafe_paths(self):
        for path in (
            "../escape",
            "/tmp/escape",
            "src/backend/.agents",
            "src/backend/debug",
            "src/backend/debug/../config",
            "src/backend/debug/.env",
            "src/backend/debug/x/../../escape",
        ):
            with self.subTest(path=path):
                r = self.cli("configure", "--source-root", self.repo, "--share", path, ok=False)
                self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.repo / ".git/worktree-bootstrap/config.json").exists())

    def test_rejects_foreign_source_repository(self):
        foreign = self.base / "foreign"
        foreign.mkdir()
        self.git("init", str(foreign))
        self.assertNotEqual(self.cli("configure", "--source-root", foreign, "--share", SHARE, ok=False).returncode, 0)

    def test_rejects_tracked_target(self):
        self.configure()
        p = self.target / SHARE
        p.mkdir(parents=True)
        (p / "tracked").write_text("tracked")
        self.git("add", "-f", str(p / "tracked"), cwd=self.target)
        self.assertNotEqual(self.cli("apply", ok=False).returncode, 0)
        self.assertEqual((p / "tracked").read_text(), "tracked")

    def test_missing_checkout_instructions_reported(self):
        self.configure()
        (self.target / "AGENTS.md").unlink()
        self.assertNotEqual(self.cli("check", ok=False).returncode, 0)
        self.assertIn("AGENTS.md", self.cli("check", ok=False).stdout)

    def test_source_checkout_not_relinked(self):
        self.configure()
        self.cli("apply", cwd=self.repo)
        self.assertFalse((self.repo / SHARE).is_symlink())

    def test_hook_runs_on_creation_and_checkout_without_branch_script(self):
        self.configure()
        self.cli("install-hook")
        new = self.base / "created by git"
        self.git("worktree", "add", "--detach", str(new))
        self.assertTrue((new / SHARE).is_symlink())
        self.assertFalse((new / "agent/shared/tools/worktree-bootstrap/bootstrap.py").exists())
        self.git("checkout", "--detach", "HEAD", cwd=new)
        self.cli("check", cwd=new)
        self.cli("install-hook")

    def test_install_hook_with_explicit_bare_policy_and_separate_git_directory(self):
        common = self.base / "separate git directory"
        self.git("init", "--separate-git-dir", common)
        self.git("worktree", "repair")
        self.env["GIT_CONFIG_GLOBAL"] = str(self.base / "global gitconfig")
        self.git("config", "--global", "safe.bareRepository", "explicit")
        self.configure()
        self.cli("install-hook")
        self.assertTrue((common / "hooks/post-checkout").is_file())
        new = self.base / "strict policy tree"
        self.git("worktree", "add", "--detach", str(new))
        self.assertTrue((new / SHARE).is_symlink())
        self.cli("check", cwd=new)
        self.assertEqual(self.git("config", "--global", "--get", "safe.bareRepository").stdout.strip(), "explicit")

    def test_hook_preserves_checkout_success_on_material_conflict(self):
        self.configure()
        self.cli("install-hook")
        p = self.target / SHARE
        p.mkdir(parents=True)
        result = self.git("checkout", "--detach", "HEAD", cwd=self.target)
        self.assertIn("WARNING", result.stderr)
        self.assertFalse(p.is_symlink())

    def test_no_checkout_needs_explicit_apply(self):
        self.configure()
        self.cli("install-hook")
        new = self.base / "no checkout"
        self.git("worktree", "add", "--no-checkout", "--detach", str(new))
        self.assertFalse((new / SHARE).exists())

    def test_existing_hook_and_custom_hookspath_are_not_replaced(self):
        self.configure()
        hook = self.repo / ".git/hooks/post-checkout"
        hook.write_text("#!/bin/sh\necho existing\n")
        self.assertNotEqual(self.cli("install-hook", ok=False).returncode, 0)
        self.assertEqual(hook.read_text(), "#!/bin/sh\necho existing\n")
        hook.unlink()
        self.git("config", "core.hooksPath", "custom hooks")
        self.assertNotEqual(self.cli("install-hook", ok=False).returncode, 0)
        self.assertFalse(hook.exists())

    def test_rejects_nonignored_material_target(self):
        self.configure()
        (self.target / ".gitignore").write_text(".agents/\n")
        self.assertNotEqual(self.cli("apply", ok=False).returncode, 0)
        self.assertFalse((self.target / SHARE).exists())

    def test_policy_replacement_is_explicit(self):
        self.configure()
        self.assertNotEqual(self.cli("configure", "--source-root", self.repo, "--share", SHARE, ok=False).returncode, 0)
        self.cli("configure", "--source-root", self.repo, "--share", SHARE, "--replace")

    def test_rejects_source_symlink_and_overlapping_shares(self):
        self.configure()
        topic = self.repo / SHARE
        (topic / "evidence.txt").unlink()
        topic.rmdir()
        topic.symlink_to(self.base, target_is_directory=True)
        self.assertNotEqual(self.cli("apply", ok=False).returncode, 0)
        self.assertNotEqual(
            self.cli(
                "configure",
                "--source-root",
                self.repo,
                "--share",
                SHARE,
                "--share",
                SHARE + "/child",
                "--replace",
                ok=False,
            ).returncode,
            0,
        )

    def test_empty_hookspath_is_detected_as_custom_configuration(self):
        self.configure()
        self.git("config", "core.hooksPath", "")
        self.assertNotEqual(self.cli("install-hook", ok=False).returncode, 0)
        self.assertFalse((self.repo / ".git/hooks/post-checkout").exists())

    def test_hookspath_in_newline_named_worktree_is_detected(self):
        self.configure()
        self.git("config", "extensions.worktreeConfig", "true")
        odd = self.base / "tree\nwith newline"
        self.git("worktree", "add", "--detach", str(odd))
        self.git("config", "--worktree", "core.hooksPath", "custom", cwd=odd)
        self.assertNotEqual(self.cli("install-hook", ok=False).returncode, 0)

    def test_deleted_tracked_ancestor_is_not_recreated_as_directory(self):
        self.configure()
        p = self.target / "src/backend/debug"
        p.write_text("tracked ancestor")
        self.git("add", "-f", str(p), cwd=self.target)
        p.unlink()
        self.assertNotEqual(self.cli("apply", ok=False).returncode, 0)
        self.assertFalse(p.exists())

    def test_control_characters_in_share_paths_are_rejected(self):
        for code in (9, 10, 13, 127):
            with self.subTest(code=code):
                share = "src/backend/debug/top" + chr(code) + "ic/task"
                self.assertNotEqual(
                    self.cli(
                        "configure", "--source-root", self.repo, "--share", share, "--replace", ok=False
                    ).returncode,
                    0,
                )

    def test_check_does_not_require_installed_hook(self):
        self.configure()
        self.cli("apply")
        self.assertFalse((self.repo / ".git/hooks/post-checkout").exists())

    def test_tampered_config_is_validated_on_every_run(self):
        self.configure()
        config = self.repo / ".git/worktree-bootstrap/config.json"
        data = json.loads(config.read_text())
        data["shares"] = ["../escape"]
        config.write_text(json.dumps(data))
        self.assertNotEqual(self.cli("apply", ok=False).returncode, 0)


if __name__ == "__main__":
    unittest.main()
