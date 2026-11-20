"""独立CLI的真实子进程/文件测试，不启动Django或连接数据库。"""
import gzip
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "support-files/database/backup_mysql.py"
FAKE_CLIENT = r'''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['FAKE_CALLS'], 'a') as f:
    f.write(json.dumps({'program': Path(sys.argv[0]).name, 'args': args,
                        'password_env': 'MYSQL_PWD' in os.environ,
                        'login_file': os.environ.get('MYSQL_TEST_LOGIN_FILE'),
                        'pid': os.getpid()}) + '\n')
if '--version' in args:
    print(Path(sys.argv[0]).name + '  Ver 8.0.46 for Linux (MySQL Community Server - GPL)')
elif '--help' in args:
    print('--no-tablespaces' if os.environ.get('FAKE_NO_COLUMN_STATS') else '--column-statistics --no-tablespaces')
elif Path(sys.argv[0]).name == 'mysql':
    db = next(a.split('=', 1)[1] for a in args if a.startswith('--database='))
    print('5.7.44\t' + db + '\tfixture-server\t3306')
    print('1' if os.environ.get('FAKE_MODE') == 'non_innodb' else '0')
    print(os.environ.get('FAKE_DATABASE_DEFAULTS', 'utf8mb4\tutf8mb4_bin'))
else:
    if any(a.startswith('--connect-timeout') for a in args):
        print('mysqldump: unknown option connect-timeout', file=sys.stderr)
        sys.exit(2)
    mode = os.environ.get('FAKE_MODE', 'ok')
    if mode == 'empty':
        sys.exit(0)
    if mode == 'empty_database':
        print('-- MySQL dump\n-- Dump completed')
        sys.exit(0)
    print('-- MySQL dump\nCREATE TABLE example (v TEXT);', flush=True)
    if mode == 'fail':
        print('sensitive-fixture-password', file=sys.stderr)
        sys.exit(7)
    if mode == 'slow':
        Path(os.environ['FAKE_READY']).write_text(str(os.getpid()))
        time.sleep(30)
    if mode != 'empty_database':
        for _ in range(32):
            print("INSERT INTO example VALUES ('中文😀" + 'x' * 32768 + "');")
    print('-- Dump completed')
'''


class MysqlBackupCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "client.cnf"
        self.config.write_text('[client]\npassword="sensitive-fixture-password"\n')
        self.config.chmod(0o600)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("mysql", "mysqldump"):
            path = self.bin / name
            path.write_text(FAKE_CLIENT.replace("#!/usr/bin/env python3", f"#!{sys.executable}"))
            path.chmod(0o700)
        self.out = self.root / "backups"
        self.env = {
            **os.environ,
            "FAKE_CALLS": str(self.root / "calls.jsonl"),
            "MYSQL_PWD": "sensitive-fixture-password",
            "MYSQL_TEST_LOGIN_FILE": str(self.root / "untrusted-login"),
        }

    def backup_args(self):
        return [
            "backup",
            "--host",
            "127.0.0.1",
            "--port",
            "3357",
            "--user",
            "backup_user",
            "--database",
            "audit-test",
            "--defaults-file",
            str(self.config),
            "--output-dir",
            str(self.out),
            "--mysql",
            str(self.bin / "mysql"),
            "--mysqldump",
            str(self.bin / "mysqldump"),
        ]

    def cli(self, *args, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            env=env or self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def good_backup(self, mode="ok"):
        result = self.cli(*self.backup_args(), env={**self.env, "FAKE_MODE": mode})
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(json.loads(result.stdout)["backup_dir"]), result

    def test_streamed_backup_is_private_complete_and_verifiable_without_clients(self):
        bundle, result = self.good_backup()
        manifest = json.loads((bundle / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["database"], "audit-test")
        self.assertEqual(manifest["server"]["version"], "5.7.44")
        self.assertIn("8.0.46", manifest["clients"]["mysqldump"])
        sql = gzip.decompress((bundle / "database.sql.gz").read_bytes())
        self.assertIn("中文😀".encode(), sql)
        self.assertGreater(len(sql), 1024 * 1024)
        self.assertEqual(bundle.stat().st_mode & 0o777, 0o700)
        self.assertEqual(sorted(f.name for f in bundle.iterdir()), ["database.sql.gz", "manifest.json"])
        for file in bundle.iterdir():
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("sensitive-fixture-password", result.stdout + result.stderr + json.dumps(manifest))
        calls = [json.loads(x) for x in (self.root / "calls.jsonl").read_text().splitlines()]
        for call in calls:
            self.assertTrue(call["args"][0].startswith("--defaults-file="))
            self.assertFalse(call["password_env"])
            self.assertNotEqual(call["login_file"], self.env["MYSQL_TEST_LOGIN_FILE"])
            self.assertNotIn("sensitive-fixture-password", json.dumps(call))
        dump = next(c["args"] for c in calls if c["program"] == "mysqldump" and "--single-transaction" in c["args"])
        self.assertEqual(dump[-1], "audit-test")
        self.assertIn("--column-statistics=0", dump)
        self.assertIn("--routines", dump)
        self.assertIn("--events", dump)
        self.assertIn("--triggers", dump)
        self.assertNotIn("--databases", dump)
        self.bin.rename(self.root / "removed-clients")
        self.config.unlink()
        checked = self.cli("verify", "--backup-dir", str(bundle))
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_failed_dump_with_partial_sql_and_empty_output_publish_nothing(self):
        for mode in ("fail", "empty"):
            with self.subTest(mode=mode):
                result = self.cli(*self.backup_args(), env={**self.env, "FAKE_MODE": mode})
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("sensitive-fixture-password", result.stdout + result.stderr)
                self.assertEqual(list(self.out.iterdir()), [])

    def test_empty_database_dump_with_sql_header_is_allowed(self):
        self.config.chmod(0o400)
        bundle, _ = self.good_backup("empty_database")
        self.assertEqual(self.cli("verify", "--backup-dir", str(bundle)).returncode, 0)

    def test_column_statistics_option_is_only_added_when_client_supports_it(self):
        result = self.cli(*self.backup_args(), env={**self.env, "FAKE_NO_COLUMN_STATS": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(x) for x in (self.root / "calls.jsonl").read_text().splitlines()]
        dump = next(c["args"] for c in calls if "--single-transaction" in c["args"])
        self.assertNotIn("--column-statistics=0", dump)

    def test_non_innodb_preflight_refuses_before_dump(self):
        result = self.cli(*self.backup_args(), env={**self.env, "FAKE_MODE": "non_innodb"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.out.iterdir()), [])
        calls = (self.root / "calls.jsonl").read_text()
        self.assertNotIn("--single-transaction", calls)

    def test_private_option_file_permissions_and_scope_are_enforced(self):
        cases = [
            ("[client]\npassword=secret\n", 0o644),
            ("[mysqldump]\nall-databases\n", 0o600),
            ("[client]\nwhere=id>0\n", 0o600),
            ("!include /tmp/other.cnf\n[client]\npassword=secret\n", 0o600),
            ("[client]\nignore-table=a.b\n", 0o600),
            ("[client]\npassword=secret\n    all-databases\n", 0o600),
        ]
        for content, mode in cases:
            with self.subTest(content=content, mode=mode):
                self.config.write_text(content)
                self.config.chmod(mode)
                result = self.cli(*self.backup_args())
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root / "calls.jsonl").exists())

    def test_defaults_symlink_is_rejected(self):
        real = self.root / "real.cnf"
        self.config.rename(real)
        self.config.symlink_to(real)
        self.assertNotEqual(self.cli(*self.backup_args()).returncode, 0)

    def test_existing_backup_is_not_overwritten(self):
        first, _ = self.good_backup()
        digest = hashlib.sha256((first / "database.sql.gz").read_bytes()).hexdigest()
        second, _ = self.good_backup()
        self.assertNotEqual(first, second)
        self.assertEqual(hashlib.sha256((first / "database.sql.gz").read_bytes()).hexdigest(), digest)

    def test_backup_preserves_database_default_charset_and_collation(self):
        for character_set, collation in (("utf8mb4", "utf8mb4_bin"), ("latin1", "latin1_swedish_ci")):
            with self.subTest(character_set=character_set):
                self.env["FAKE_DATABASE_DEFAULTS"] = character_set + "\t" + collation
                bundle, _ = self.good_backup()
                manifest = json.loads((bundle / "manifest.json").read_text())
                self.assertEqual(
                    manifest.get("database_defaults"), {"character_set": character_set, "collation": collation}
                )

    def test_verify_requires_valid_database_defaults(self):
        bundle, _ = self.good_backup()
        path = bundle / "manifest.json"
        original = path.read_bytes()
        for defaults in (
            "missing",
            None,
            {},
            {"character_set": "utf8mb4"},
            {"character_set": True, "collation": "utf8mb4_bin"},
            {"character_set": "utf8mb4", "collation": "utf8mb4_bin; DROP DATABASE other"},
        ):
            with self.subTest(defaults=defaults):
                data = json.loads(original)
                if defaults == "missing":
                    data.pop("database_defaults", None)
                else:
                    data["database_defaults"] = defaults
                path.write_text(json.dumps(data))
                self.assertNotEqual(self.cli("verify", "--backup-dir", str(bundle)).returncode, 0)

    def test_verify_rejects_checksum_corruption_missing_and_incomplete_manifest(self):
        bundle, _ = self.good_backup()
        manifest_path = bundle / "manifest.json"
        original = manifest_path.read_bytes()
        for mutation in ("incomplete", "path", "sha", "missing"):
            with self.subTest(mutation=mutation):
                data = json.loads(original)
                if mutation == "incomplete":
                    data["status"] = "started"
                elif mutation == "path":
                    data["dump"]["name"] = "../outside.gz"
                elif mutation == "sha":
                    data["dump"]["sha256"] = "0" * 64
                else:
                    del data["dump"]
                manifest_path.write_text(json.dumps(data))
                self.assertNotEqual(self.cli("verify", "--backup-dir", str(bundle)).returncode, 0)
        manifest_path.write_bytes(original)
        (bundle / "database.sql.gz").write_bytes(b"corrupt gzip")
        self.assertNotEqual(self.cli("verify", "--backup-dir", str(bundle)).returncode, 0)

    def test_verify_rejects_invalid_gzip_even_if_compressed_sha_matches(self):
        bundle, _ = self.good_backup()
        dump = bundle / "database.sql.gz"
        dump.write_bytes(dump.read_bytes()[:-8])
        manifest_path = bundle / "manifest.json"
        data = json.loads(manifest_path.read_text())
        data["dump"]["size_bytes"] = dump.stat().st_size
        data["dump"]["sha256"] = hashlib.sha256(dump.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(data))
        self.assertNotEqual(self.cli("verify", "--backup-dir", str(bundle)).returncode, 0)

    def test_verify_requires_complete_target_server_client_and_time_metadata(self):
        bundle, _ = self.good_backup()
        path = bundle / "manifest.json"
        original = path.read_bytes()
        for key, value in (("server", {}), ("clients", {}), ("target", {}), ("completed_at_utc", "invalid")):
            with self.subTest(key=key):
                data = json.loads(original)
                data[key] = value
                path.write_text(json.dumps(data))
                self.assertNotEqual(self.cli("verify", "--backup-dir", str(bundle)).returncode, 0)

    def test_verify_refuses_payload_symlink(self):
        bundle, _ = self.good_backup()
        dump = bundle / "database.sql.gz"
        outside = self.root / "outside.gz"
        dump.rename(outside)
        dump.symlink_to(outside)
        self.assertNotEqual(self.cli("verify", "--backup-dir", str(bundle)).returncode, 0)

    def test_sigterm_during_dump_cleans_partial_bundle_and_stops_child(self):
        ready = self.root / "ready"
        proc = subprocess.Popen(
            [sys.executable, str(SCRIPT), *self.backup_args()],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**self.env, "FAKE_MODE": "slow", "FAKE_READY": str(ready)},
            text=True,
        )
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists())
            proc.send_signal(signal.SIGTERM)
            stdout, stderr = proc.communicate(timeout=5)
            self.assertNotEqual(proc.returncode, 0)
            self.assertNotIn("sensitive-fixture-password", stdout + stderr)
            self.assertEqual(list(self.out.iterdir()), [])
            with self.assertRaises(ProcessLookupError):
                os.kill(int(ready.read_text()), 0)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()


if __name__ == "__main__":
    unittest.main()
