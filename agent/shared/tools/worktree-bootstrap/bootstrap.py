#!/usr/bin/env python3
"""Opt-in, repository-local worktree material bootstrap (Python 3.9+)."""
import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

STATE = "worktree-bootstrap"
MARKER = "# bk-audit-worktree-bootstrap-v1"


def git(root, *args, allow_missing=False):
    env = os.environ.copy()
    for name in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX"):
        env.pop(name, None)
    result = subprocess.run(["git", "-C", str(root), *args], env=env, text=True, capture_output=True)
    if result.returncode and not (allow_missing and result.returncode == 1):
        raise ValueError(result.stderr.strip() or "Git command failed")
    return result.stdout.removesuffix("\n")


def identity(path):
    root = Path(git(path, "rev-parse", "--show-toplevel")).resolve()
    common = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
    return root, common


def share_path(value):
    if not isinstance(value, str) or "\\" in value or "\x00" in value:
        raise ValueError("Invalid share path")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Control characters are not allowed in share paths")
    parts = value.split("/")
    if parts[:3] != ["src", "backend", "debug"] or len(parts) < 4:
        raise ValueError("Only explicit topics below src/backend/debug/ may be shared")
    if any(not part or part.startswith(".") for part in parts):
        raise ValueError("Absolute, hidden and traversal paths are not allowed")
    return PurePosixPath(value)


def no_link_parents(root, rel):
    current = root
    for part in rel.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlink ancestor: " + str(current))
        if current.exists() and not current.is_dir():
            raise ValueError("Non-directory ancestor: " + str(current))


def state_dir(common):
    state = common / STATE
    if state.is_symlink():
        raise ValueError("State directory must not be a symlink")
    return state


def atomic_write(path, content, mode=0o600):
    if path.is_symlink():
        raise ValueError("Refusing to replace symlink: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as out:
            name = out.name
            out.write(content)
            os.fchmod(out.fileno(), mode)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def validate_config(data, common):
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unsupported configuration")
    source_value = data.get("source_root")
    if not isinstance(source_value, str) or not Path(source_value).is_absolute():
        raise ValueError("source_root must be an absolute worktree root")
    source, source_common = identity(source_value)
    if source != Path(source_value).resolve() or source_common != common:
        raise ValueError("Source must be a worktree root in this same repository")
    shares = data.get("shares")
    if not isinstance(shares, list) or not shares:
        raise ValueError("At least one explicitly approved share is required")
    paths = [share_path(value) for value in shares]
    for i, path in enumerate(paths):
        for other in paths[:i]:
            if path == other or path in other.parents or other in path.parents:
                raise ValueError("Duplicate or overlapping shares")
    return source, paths


def load_config(common):
    path = state_dir(common) / "config.json"
    if path.is_symlink():
        raise ValueError("Configuration must not be a symlink")
    with path.open(encoding="utf-8") as stream:
        return validate_config(json.load(stream), common)


def check_or_apply(root, common, apply):
    policy = state_dir(common) / "config.json"
    if not apply and not os.path.lexists(policy):
        source, shares = None, []
        print("INFO no material sharing policy; skipping shared topic checks")
    else:
        source, shares = load_config(common)
    failures = 0
    tracked = set(git(root, "ls-files", "-z").split("\x00"))
    for rel in ("AGENTS.md", "src/backend/AGENTS.md"):
        p = root / rel
        if p.is_file() and not p.is_symlink() and git(root, "ls-files", "--", rel):
            print("OK checkout instructions:", rel)
        else:
            print("MISSING/UNTRACKED checkout instructions:", rel, "(not copied from source)")
            failures += 1
    for rel in shares:
        try:
            no_link_parents(source, rel)
            no_link_parents(root, rel)
            src, dst = source / rel, root / rel
            if src.is_symlink() or not src.is_dir():
                raise ValueError("Source topic missing or symlink: " + str(src))
            ancestors = {str(parent) for parent in rel.parents}
            if any(
                name == str(rel) or name.startswith(str(rel) + "/") or name in ancestors for name in tracked if name
            ):
                raise ValueError("Target or ancestor contains tracked files: " + str(rel))
            if not git(root, "check-ignore", "--", str(rel), allow_missing=True):
                raise ValueError("Target must be Git-ignored: " + str(rel))
            if root == source:
                print("OK source topic:", rel)
                continue
            if dst.is_symlink() and dst.resolve() == src:
                print("OK shared topic:", rel)
            elif os.path.lexists(dst):
                raise ValueError("Existing target preserved: " + str(dst))
            elif apply:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.symlink_to(src, target_is_directory=True)
                print("LINKED topic:", rel)
            else:
                raise ValueError("Share not prepared: " + str(rel))
        except (ValueError, OSError, RuntimeError) as error:
            print("CONFLICT:", error)
            failures += 1
    found_skills = False
    for location in (".agents/skills", "src/backend/.agents/skills", "src/frontend/.agents/skills"):
        if any(p.is_file() and os.access(p, os.R_OK) for p in (root / location).glob("*/SKILL.md")):
            print("INFO skill files found:", location)
            found_skills = True
    if not found_skills:
        print("INFO no project skill files found in root, backend or frontend .agents/skills")
    print("INFO client discovery and versions were not checked")
    for location in ("src/backend/.env", "src/backend/config/local_settings.py", "src/backend/.venv"):
        path = root / location
        status = "missing"
        if path.is_symlink():
            status = "symlink" if path.exists() else "broken symlink"
        elif path.exists():
            status = "present"
        print(f"INFO backend path: {location} ({status})")
    return 1 if failures else 0


def install_hook(common):
    # A repository with per-worktree hooksPath needs an explicit integration decision.
    for entry in git(common, "--git-dir=" + str(common), "worktree", "list", "--porcelain", "-z").split("\x00"):
        if entry.startswith("worktree "):
            worktree = entry[len("worktree ") :]
            if Path(worktree).exists() and git(
                worktree, "config", "--null", "--get-all", "core.hooksPath", allow_missing=True
            ):
                raise ValueError("core.hooksPath configured; integrate explicitly, not replaced")
    hook = common / "hooks/post-checkout"
    if hook.parent.is_symlink() or hook.is_symlink():
        raise ValueError("Hook or hooks directory is a symlink")
    body = "\n".join(
        [
            "#!/bin/sh",
            MARKER,
            '[ "$3" = "1" ] || exit 0',
            'common=$(git rev-parse --path-format=absolute --git-common-dir) || exit 0',
            'if ! ' + shlex.quote(sys.executable) + ' "$common/' + STATE + '/bootstrap.py" apply; then',
            '  echo "WARNING: worktree created/checked out, but materials need attention; run bootstrap check." >&2',
            "fi",
            "exit 0",
            "",
        ]
    )
    if hook.exists() and hook.read_text(encoding="utf-8") != body:
        raise ValueError("Existing post-checkout preserved; explicit integration required")
    state = state_dir(common)
    # Pin the reviewed implementation, never execute a script from an arbitrary new branch.
    atomic_write(state / "bootstrap.py", Path(__file__).read_text(encoding="utf-8"))
    atomic_write(hook, body, mode=0o755)
    print("INSTALLED repository-local hook and reviewed runner snapshot; no global config changed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", default=".", help="worktree or directory within it")
    subs = parser.add_subparsers(dest="command", required=True)
    config = subs.add_parser("configure", help="explicitly save local sharing policy")
    config.add_argument("--source-root", required=True)
    config.add_argument("--share", action="append", required=True, help="approved debug topic; repeatable")
    config.add_argument("--replace", action="store_true", help="replace existing local policy")
    subs.add_parser("check", help="read-only readiness check")
    subs.add_parser("apply", help="create missing links without replacing existing paths")
    subs.add_parser("install-hook", help="opt-in hook installation/update with stable runner snapshot")
    args = parser.parse_args()
    try:
        root, common = identity(args.worktree)
        if args.command == "configure":
            data = {"version": 1, "source_root": str(Path(args.source_root).absolute()), "shares": args.share}
            validate_config(data, common)
            path = state_dir(common) / "config.json"
            if os.path.lexists(path) and not args.replace:
                raise ValueError("Configuration exists; review it and use --replace explicitly")
            atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            print("SAVED local policy (does not apply links or install hook)")
            return 0
        if args.command == "install-hook":
            load_config(common)
            install_hook(common)
            return 0
        return check_or_apply(root, common, args.command == "apply")
    except (ValueError, OSError, RuntimeError) as error:
        print("ERROR:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
