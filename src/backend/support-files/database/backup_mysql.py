#!/usr/bin/env python3
"""独立的MySQL单库备份与本地完整性核验；不加载Django，不提供恢复命令。"""
import argparse
import configparser
import gzip
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import uuid
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
DUMP_NAME = "database.sql.gz"
DATABASE_PATTERN = r"[A-Za-z0-9_][A-Za-z0-9_-]{0,63}"
DATABASE_ATTRIBUTE_PATTERN = r"[A-Za-z][A-Za-z0-9_]{0,63}"
CONNECTION_OPTIONS = {
    "host",
    "port",
    "user",
    "password",
    "ssl-mode",
    "ssl-ca",
    "ssl-capath",
    "ssl-cert",
    "ssl-key",
    "ssl-cipher",
    "ssl-crl",
    "ssl-crlpath",
    "ssl-verify-server-cert",
    "tls-version",
    "get-server-public-key",
    "server-public-key-path",
    "default-auth",
}
DUMP_OPTIONS = [
    "--single-transaction",
    "--quick",
    "--routines",
    "--events",
    "--triggers",
    "--hex-blob",
    "--set-gtid-purged=OFF",
    "--no-tablespaces",
    "--skip-lock-tables",
]


class BackupError(Exception):
    """可安全展示的阶段错误，不包含凭据、任意客户端输出或SQL内容。"""


def utc_now():
    """返回带时区的UTC完成/开始时间。"""
    return datetime.now(timezone.utc).isoformat()


def validate_database_defaults(value):
    """保留原库默认属性，并限制为可安全用于隔离建库的MySQL标识符。"""
    if not isinstance(value, dict) or any(
        not isinstance(value.get(key), str) or not re.fullmatch(DATABASE_ATTRIBUTE_PATTERN, value[key])
        for key in ("character_set", "collation")
    ):
        raise BackupError("Missing or invalid database default charset/collation")
    return {key: value[key] for key in ("character_set", "collation")}


def open_regular(path):
    """只读打开非软链的普通文件，避免凭据和bundle文件指向其他目标。"""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise BackupError("Expected a regular file")
    return os.fdopen(fd, "rb")


def read_defaults(path):
    """校验并快照私有连接配置，拒绝包含指令和改变导出范围的选项。"""
    with open_regular(path) as stream:
        info = os.fstat(stream.fileno())
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) not in (0o400, 0o600):
            raise BackupError("Defaults file must belong to the current user and have mode 0400 or 0600")
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise BackupError("Defaults file is too large")
    try:
        text = raw.decode("utf-8")
        for line in text.splitlines():
            value = line.strip()
            if not value or value.startswith(("#", ";")):
                continue
            if value != "[client]" and ("=" not in value or value.startswith("!")):
                raise BackupError("Only a [client] group with explicit connection options is allowed")
        parser = configparser.ConfigParser(interpolation=None, empty_lines_in_values=False)
        parser.read_string(text)
        if parser.defaults() or parser.sections() != ["client"]:
            raise BackupError("Only the [client] option group is allowed")
        if any(key.replace("_", "-") not in CONNECTION_OPTIONS for key in parser["client"]):
            raise BackupError("Defaults file contains an option outside the connection allowlist")
        if any("\n" in value or "\r" in value for value in parser["client"].values()):
            raise BackupError("Multiline option values are not supported")
    except (UnicodeError, configparser.Error) as error:
        raise BackupError("Invalid defaults file") from error
    return raw


def private_write(path, content):
    """排他创建私有文件并落盘，绝不截断已有文件。"""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def client_output(command, env, stage):
    """获取有限元数据；客户端错误输出可能带敏感信息，不转发到console。"""
    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise BackupError(f"{stage} failed (exit {result.returncode})")
    return result.stdout.decode("utf-8", errors="strict")


def client_version(binary, defaults, env, program):
    """识别MySQL客户端版本；不将MariaDB或未知客户端假定为已支持。"""
    version = client_output([binary, defaults, "--version"], env, f"{program} version check").strip()
    if (
        "MariaDB" in version
        or not re.fullmatch(rf"{program}\s+Ver\s+.+", version)
        or not re.search(r"\b(?:5\.7|8\.0)\.\d+\b", version)
    ):
        raise BackupError("Only MySQL 5.7/8.0 clients are supported; validate the exact target combination")
    return version


def stream_dump(command, env, path):
    """按块压缩stdout；即便输出可解压，dump非零退出也不能视为成功。"""
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    size, has_sql = 0, False
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output, gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0) as zipped:
            with process.stdout:
                while True:
                    chunk = process.stdout.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    has_sql = has_sql or bool(chunk.strip())
                    zipped.write(chunk)
            code = process.wait()
            if code:
                raise BackupError(f"mysqldump failed (exit {code}); no backup published")
            if not has_sql:
                raise BackupError("mysqldump returned empty SQL; no backup published")
            zipped.close()
            output.flush()
            os.fsync(output.fileno())
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        if process.stdout is not None:
            process.stdout.close()
    return size


def inspect_dump(path):
    """流式核gzip CRC、压缩摘要和SQL字节数，不把整库载入内存。"""
    digest = hashlib.sha256()
    with open_regular(path) as stream:
        info = os.fstat(stream.fileno())
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
        stream.seek(0)
        sql_bytes = 0
        with gzip.GzipFile(fileobj=stream, mode="rb") as zipped:
            for chunk in iter(lambda: zipped.read(CHUNK_SIZE), b""):
                sql_bytes += len(chunk)
    if not sql_bytes:
        raise BackupError("Compressed SQL is empty")
    return {"name": DUMP_NAME, "size_bytes": info.st_size, "sha256": digest.hexdigest(), "sql_bytes": sql_bytes}


def backup(args):
    """核目标和事务引擎，完成导出后原子发布唯一的新bundle目录。"""
    if not re.fullmatch(DATABASE_PATTERN, args.database):
        raise BackupError("Unsupported database name; use up to 64 letters, digits, underscores or hyphens")
    if not args.host or not args.user or any(c in args.host + args.user for c in "\0\n\r"):
        raise BackupError("Explicit host and user are required")
    if not 1 <= args.port <= 65535:
        raise BackupError("Invalid TCP port")
    raw = read_defaults(args.defaults_file)
    output = args.output_dir
    if output.is_symlink():
        raise BackupError("Output directory cannot be a symlink")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    output = output.resolve()
    started = utc_now()
    stage = Path(tempfile.mkdtemp(prefix=".partial-", dir=output))
    try:
        defaults_path = stage / "client.cnf"
        private_write(defaults_path, raw)
        defaults = f"--defaults-file={defaults_path}"
        env = os.environ.copy()
        for key in ("MYSQL_PWD", "MYSQL_HOME", "MYSQL_GROUP_SUFFIX", "MYSQL_HOST", "MYSQL_TCP_PORT", "MYSQL_UNIX_PORT"):
            env.pop(key, None)
        # MySQL即使用defaults-file也会读登录文件；指向本次私有目录内不存在的路径。
        env["MYSQL_TEST_LOGIN_FILE"] = str(stage / "unused-login-file")
        mysql_version = client_version(args.mysql, defaults, env, "mysql")
        dump_version = client_version(args.mysqldump, defaults, env, "mysqldump")
        connection = [
            "--protocol=TCP",
            f"--host={args.host}",
            f"--port={args.port}",
            f"--user={args.user}",
            "--default-character-set=utf8mb4",
        ]
        query = (
            "SELECT VERSION(), DATABASE(), @@hostname, @@port;"
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() "
            "AND table_type='BASE TABLE' AND (ENGINE IS NULL OR UPPER(ENGINE)<>'INNODB');"
            "SELECT DEFAULT_CHARACTER_SET_NAME,DEFAULT_COLLATION_NAME FROM information_schema.schemata "
            "WHERE SCHEMA_NAME=DATABASE();"
        )
        rows = client_output(
            [
                args.mysql,
                defaults,
                *connection,
                "--connect-timeout=10",
                "--batch",
                "--skip-column-names",
                "--raw",
                f"--database={args.database}",
                f"--execute={query}",
            ],
            env,
            "Read-only server preflight",
        ).splitlines()
        if len(rows) != 3 or len(rows[0].split("\t")) != 4 or rows[1] != "0" or len(rows[2].split("\t")) != 2:
            raise BackupError("Server preflight failed or non-InnoDB/unknown-engine tables were found")
        version, database, hostname, port = rows[0].split("\t")
        if database != args.database or not re.fullmatch(r"(?:5\.7|8\.0)\.\d+(?:[-.][A-Za-z0-9_.-]+)?", version):
            raise BackupError("Unexpected server database or unsupported server version")
        character_set, collation = rows[2].split("\t")
        database_defaults = validate_database_defaults({"character_set": character_set, "collation": collation})
        help_text = client_output([args.mysqldump, defaults, "--help"], env, "mysqldump capabilities check")
        options = list(DUMP_OPTIONS)
        if "--column-statistics" in help_text:
            options.append("--column-statistics=0")
        sql_bytes = stream_dump(
            [args.mysqldump, defaults, *connection, *options, args.database],
            env,
            stage / DUMP_NAME,
        )
        dump = inspect_dump(stage / DUMP_NAME)
        if dump["sql_bytes"] != sql_bytes:
            raise BackupError("Compressed SQL length mismatch")
        defaults_path.unlink()
        manifest = {
            "schema_version": 1,
            "status": "complete",
            "database": args.database,
            "database_defaults": database_defaults,
            "target": {"host": args.host, "port": args.port, "user": args.user, "protocol": "TCP"},
            "server": {"version": version, "hostname": hostname, "port": int(port)},
            "clients": {"mysql": mysql_version, "mysqldump": dump_version},
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "consistency": "InnoDB single-transaction; writes, background tasks and DDL must be paused",
            "dump_options": [*connection, *options],
            "dump": dump,
        }
        private_write(stage / "manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
        final = output / f"{args.database}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex}"
        if final.exists():
            raise BackupError("Backup destination already exists")
        os.rename(stage, final)
        return final
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def verify(directory):
    """只读核验本地成功bundle；无需数据库、配置文件或MySQL客户端。"""
    if directory.is_symlink() or not directory.is_dir():
        raise BackupError("Expected a backup directory")
    with open_regular(directory / "manifest.json") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise BackupError("Manifest is too large")
    manifest = json.loads(raw)
    if (
        not isinstance(manifest, dict)
        or type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
        or manifest.get("status") != "complete"
        or not isinstance(manifest.get("database"), str)
        or not re.fullmatch(DATABASE_PATTERN, manifest["database"])
        or not isinstance(manifest.get("dump"), dict)
    ):
        raise BackupError("Invalid or incomplete manifest")
    validate_database_defaults(manifest.get("database_defaults"))
    dump = manifest["dump"]
    if (
        dump.get("name") != DUMP_NAME
        or not isinstance(dump.get("sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", dump["sha256"])
        or any(type(dump.get(key)) is not int or dump[key] <= 0 for key in ("size_bytes", "sql_bytes"))
        or any(not isinstance(manifest.get(key), dict) for key in ("server", "clients", "target"))
        or any(not isinstance(manifest.get(key), str) for key in ("started_at_utc", "completed_at_utc"))
    ):
        raise BackupError("Invalid manifest metadata or dump filename")
    for metadata in (manifest["target"], manifest["server"]):
        if type(metadata.get("port")) is not int or not 1 <= metadata["port"] <= 65535:
            raise BackupError("Invalid manifest target or server port")
    if (
        manifest["target"].get("protocol") != "TCP"
        or any(
            not isinstance(manifest["target"].get(key), str) or not manifest["target"][key] for key in ("host", "user")
        )
        or any(
            not isinstance(manifest["server"].get(key), str) or not manifest["server"][key]
            for key in ("version", "hostname")
        )
        or any(
            not isinstance(manifest["clients"].get(key), str) or not manifest["clients"][key]
            for key in ("mysql", "mysqldump")
        )
    ):
        raise BackupError("Incomplete manifest target, server or client metadata")
    started = datetime.fromisoformat(manifest["started_at_utc"])
    completed = datetime.fromisoformat(manifest["completed_at_utc"])
    if started.utcoffset() != timedelta(0) or completed.utcoffset() != timedelta(0) or completed < started:
        raise BackupError("Invalid manifest UTC time interval")
    if inspect_dump(directory / DUMP_NAME) != dump:
        raise BackupError("Backup digest, size or SQL length does not match manifest")
    return manifest


class SafeArgumentParser(argparse.ArgumentParser):
    """错误参数不原样回显，防止误传密码时再次进入console。"""

    def error(self, message):
        raise BackupError("Invalid arguments; use --help")


def main(argv=None):
    """返回0表示完整备份/核验成功，非0不得作为可恢复备份交付。"""
    parser = SafeArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=SafeArgumentParser)
    create = commands.add_parser("backup", help="Back up one explicit MySQL database")
    for name in ("host", "user", "database"):
        create.add_argument(f"--{name}", required=True)
    create.add_argument("--port", type=int, default=3306)
    create.add_argument("--defaults-file", type=Path, required=True)
    create.add_argument("--output-dir", type=Path, required=True)
    create.add_argument("--mysql", default="mysql")
    create.add_argument("--mysqldump", default="mysqldump")
    check = commands.add_parser("verify", help="Verify a local backup without database access")
    check.add_argument("--backup-dir", type=Path, required=True)
    try:
        args = parser.parse_args(argv)
        if args.command == "backup":
            result = {"status": "complete", "backup_dir": str(backup(args))}
        else:
            verify(args.backup_dir)
            result = {"status": "verified", "backup_dir": str(args.backup_dir)}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except BackupError as error:
        print(f"Error: {error}", file=sys.stderr)
    except KeyboardInterrupt:
        print("Error: interrupted; incomplete backup is not published", file=sys.stderr)
        return 130
    except (OSError, ValueError, EOFError, zlib.error, subprocess.SubprocessError):
        print("Error: filesystem, compression or client operation failed; no success confirmed", file=sys.stderr)
    return 1


def interrupt(signum, frame):
    """SIGTERM沿正常异常路径结束dump子进程并清理未发布目录。"""
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupt)
    sys.exit(main())
