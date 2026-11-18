# 审计 MySQL 单库备份

`backup_mysql.py` 只提供 `backup` 和 `verify`，不加载 Django、不读取应用配置、不导入或恢复数据库，也不备份 BKBase 平台资源。使用 Python 3.11 标准库，以及已有的官方 MySQL `mysql` / `mysqldump` 客户端；后端镜像不保证包含客户端。

## 使用前确认

- 目标环境、库名、备份账号由发布负责人明确提供，脚本不会自动选择。当前支持识别 MySQL 5.7 / 8.0 客户端和服务版本，拒绝 MariaDB 等未核实实现。目标应选经恢复验证的客户端组合；本地某个版本组合通过不代表其他环境兼容。
- 此方案要求所有基础表为 InnoDB；发现其他或未知引擎即失败。备份窗口暂停配置写入、相关后台任务及 DDL。即便预检通过，也不能在导出期间变更表结构；视图、例程和事件定义同样需要稳定。
- 备份账号须具备目标库的读取以及导出视图、例程、触发器、事件所需权限。不要为绕过失败在脚本中临时提权或改全局状态；由运维按实际服务版本配置账号。
- POSIX 环境运行，确保私有输出目录有足够空间。SQL 含完整业务数据，应作为敏感备份保管。gzip 不提供加密，SHA256 只核本地完整性，不证明产物来源可信，也不能代替恢复演练。

上述一致性与导出选项依据 [MySQL mysqldump 文档](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html)。

## 外置凭据

由运维提供当前用户拥有、权限为 `0600` 或 `0400` 的普通文件，例如 `/run/secrets/audit-backup.cnf`。不接受软链。格式仅允许一个 `[client]` 组，使用 `key=value`，例如：

```ini
[client]
password="由密钥系统写入，不放进命令行"
ssl-mode=VERIFY_IDENTITY
ssl-ca=/run/secrets/mysql-ca.pem
```

按实际环境选择 TLS 配置，不要求把示例原样用于未配置 TLS 的本地实例。只允许连接、凭据和 TLS 选项；拒绝包含指令、其他组、过滤条件或改变导出范围的选项。支持的选项见脚本 `CONNECTION_OPTIONS`。不支持多行值；保留 MySQL 原有的引号/转义规则。

脚本把已验证的原始内容复制到本次私有临时目录，以 `--defaults-file` 作为客户端第一选项；显式 host / port / user 覆盖文件中的对应值。不传口令参数、不回显配置或任意客户端 stderr，不把凭据文件放入成功 bundle。脚本移除 `MYSQL_PWD` 等隐式连接变量，并用 `MYSQL_TEST_LOGIN_FILE` 隔离用户登录文件；原因见 [MySQL option-file handling](https://dev.mysql.com/doc/refman/8.0/en/option-file-options.html)。

## 备份和离线核验

以下占位值必须替换为已经确认的目标，不从应用本地配置猜测：

```bash
python3 support-files/database/backup_mysql.py backup \
  --host '<目标MySQL地址>' --port 3306 --user '<备份账号>' \
  --database '<审计实际库名>' \
  --defaults-file /run/secrets/audit-backup.cnf \
  --output-dir /secure/audit-backups
```

需要指定客户端时，增加 `--mysql /path/to/mysql --mysqldump /path/to/mysqldump`。库名支持字母、数字、下划线和连字符，最长64字符，不接受以连字符开头。连接固定使用 TCP，默认端口3306；输出记录显式连接端口和服务实际报告的内部端口。

成功退出0并输出一行 JSON，`backup_dir` 为唯一新目录。其权限为 `0700`，仅含两个 `0600` 文件：

- `database.sql.gz`：单库完整 schema、数据、routines、events、triggers。包含 `single-transaction`、`quick`、`hex-blob`、`utf8mb4`、`set-gtid-purged=OFF` 和 `no-tablespaces`；客户端支持时才增加 `column-statistics=0`。不使用 `--databases` / `--all-databases`，不改写原始 SQL、DEFINER 或库引用。
- `manifest.json`：完成标记、目标/库标识、原库 `database_defaults.character_set` / `collation`、客户端/实际服务版本、UTC时间、实际选项、压缩大小、SQL字节数及压缩文件 SHA256，不含密码。

SQL按块写入真正的 gzip 流，不把全库装入内存。dump退出0、SQL非空、gzip完整性与SHA检查通过后，才写完成 manifest 并从同文件系统的私有临时目录原子改名发布。不覆盖已有备份。空库仍应有有效dump头，不接受零字节/纯空白输出。

```bash
python3 support-files/database/backup_mysql.py verify \
  --backup-dir '/secure/audit-backups/<成功bundle目录>'
```

`verify` 只读本地文件，无需 MySQL 客户端、凭据或数据库访问。它核完成标记、元数据结构、安全文件名、大小/SHA256、gzip CRC及SQL字节数。成功退出0；缺失、篡改、损坏或不完整产物非0。它不证明 SQL 可恢复、数据属于预期时间点或权限/平台资源已可用。

当前尚未发布，最终v1格式要求数据库默认属性完整且标识符格式合法。早期缺少 `database_defaults` 的试验包仅作历史证据，不能通过当前verify，也不应手工补造元数据。

失败或 SIGINT/SIGTERM 中断时不发布成功 bundle，并清理本轮临时目录。SIGKILL、主机断电或文件系统故障可能留下 `.partial-*` 私有目录，不能将其当成功备份；由负责人核归属后处理。客户端错误只报告阶段和退出码，保留源码/权限检查以定位原因，勿为排障把凭据或SQL写入共享日志。

## 恢复演练：独立实例、原库名

正式迁移前，先在与目标同主版本的独立 MySQL 实例演练；实例不得连接生产网络、启动审计 worker 或访问 BKBase。关闭该独立实例的 event_scheduler，或确认所有待恢复事件禁用。不要改共享实例的全局变量。

在隔离实例按 manifest 的**原库名、默认字符集和排序规则**创建空库，不继承隔离实例默认值。保留原库名是为了让视图、例程等显式库引用仍然正确；未声明字符集的例程字符参数、局部变量等会继承创建时的数据库默认属性。`--default-character-set=utf8mb4` 仅设置连接，不能替代建库属性。不要改写 SQL。配置专用恢复凭据和显式连接目标，不能把原备份账号/地址直接用于恢复。

先执行上面的 `verify`，再在受控私有目录解压，分别检查两个命令退出码；不使用可能掩盖管道失败的直接恢复链：

```bash
set -euo pipefail
umask 077
BUNDLE='<成功bundle>'
RESTORE_DIR='<新建的私有恢复目录>'
RESTORE_DEFAULTS='/run/secrets/isolated-restore.cnf'
RESTORE_HOST='<隔离实例>'
RESTORE_PORT=3306
RESTORE_USER='<恢复账号>'

python3 support-files/database/backup_mysql.py verify --backup-dir "$BUNDLE"
mkdir -m 700 "$RESTORE_DIR"
python3 - "$BUNDLE/manifest.json" > "$RESTORE_DIR/database-defaults.tsv" <<'PY'
import json, re, sys
with open(sys.argv[1], encoding="utf-8") as stream:
    manifest = json.load(stream)
database = manifest["database"]
defaults = manifest["database_defaults"]
assert re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,63}", database)
for key in ("character_set", "collation"):
    assert re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", defaults[key])
print(database, defaults["character_set"], defaults["collation"], sep="\t")
PY
IFS=$'\t' read -r RESTORE_DATABASE RESTORE_CHARSET RESTORE_COLLATION < "$RESTORE_DIR/database-defaults.tsv"
printf 'CREATE DATABASE `%s` CHARACTER SET %s COLLATE %s;\n' \
  "$RESTORE_DATABASE" "$RESTORE_CHARSET" "$RESTORE_COLLATION" > "$RESTORE_DIR/create.sql"
RESTORE_CLIENT=(mysql "--defaults-file=$RESTORE_DEFAULTS" --protocol=TCP \
  "--host=$RESTORE_HOST" "--port=$RESTORE_PORT" "--user=$RESTORE_USER" --default-character-set=utf8mb4)
env -u MYSQL_PWD MYSQL_TEST_LOGIN_FILE="$RESTORE_DIR/no-login-file" \
  "${RESTORE_CLIENT[@]}" < "$RESTORE_DIR/create.sql"
gzip -dc "$BUNDLE/database.sql.gz" > "$RESTORE_DIR/restore.sql"
env -u MYSQL_PWD MYSQL_TEST_LOGIN_FILE="$RESTORE_DIR/no-login-file" \
  "${RESTORE_CLIENT[@]}" "--database=$RESTORE_DATABASE" < "$RESTORE_DIR/restore.sql"
env -u MYSQL_PWD MYSQL_TEST_LOGIN_FILE="$RESTORE_DIR/no-login-file" \
  "${RESTORE_CLIENT[@]}" "--database=$RESTORE_DATABASE" --batch --skip-column-names \
  --execute='SELECT SCHEMA_NAME,DEFAULT_CHARACTER_SET_NAME,DEFAULT_COLLATION_NAME FROM information_schema.schemata WHERE SCHEMA_NAME=DATABASE()' \
  > "$RESTORE_DIR/restored-defaults.tsv"
cmp "$RESTORE_DIR/database-defaults.tsv" "$RESTORE_DIR/restored-defaults.tsv"
```

这段是 Bash；任一步失败立即停止，建库发现同名库已存在也会失败，不自动删除旧库。按实际版本核 schema、表/视图/例程/触发器/禁用事件、行数与关键值（包括中文emoji、NULL、binary、JSON），以及 `django_migrations` 和关键审计配置/Binding可读性。通过 `information_schema.parameters` 核例程字符参数的字符集/排序规则，并在隔离环境以受控只读例程验证参数/局部变量的Unicode及大小写比较语义。完整目标恢复验证还需用隔离配置核 `manage.py migrate --plan`，不得误连原库；本地小夹具测试不能替代这一步。

保存版本、目标归属、验收和清理证据，演练通过后才推进目标环境迁移。该 SQL bundle 不包含 BKBase 资源，不支持直接宣布平台回退；平台迁移/回退和 V4 新写入后的处理沿用发布清单。

## 工具自测

不启动 Django、不连接数据库：

```bash
.venv/bin/python -m unittest tests.test_support_files.test_mysql_backup -v
```

真实小夹具验证须单独授权并限定唯一自有 probe 库；只能删除该次创建的 probe 后以同名恢复。不得读取或修改既有应用/测试库、共享中间件或 MySQL 全局状态。
