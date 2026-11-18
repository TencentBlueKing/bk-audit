"""为下游 ETL 测试提供系统初始化已经确认的 IAM Join 配置。

仅写入本地测试库；平台资源核验和未就绪保护由系统快照专项测试覆盖。
"""
from apps.meta.models import GlobalMetaConfig
from services.web.databus.collector.snapshot.system.v4 import SYSTEM_SNAPSHOT_KEYS


def seed_ready_system_snapshots(*, tenant="default", namespace="audit"):
    """按租户和项目补齐三类已就绪快照，保留实际 Redis Join 键顺序。"""
    for kind, (config_key, _) in SYSTEM_SNAPSHOT_KEYS.items():
        binding = {
            "snapshot_type": kind,
            "ready": True,
            "result_table_id": f"11_iam_{kind}",
            "redis_binding": {
                "kind": "RedisBinding",
                "tenant": tenant,
                "namespace": namespace,
                "name": f"iam_{kind}",
            },
            "redis_key_fields": ["id"] if kind == "user" else ["id", "system_id"],
        }
        GlobalMetaConfig.set(config_key, {"bkbase_v4": {tenant: {namespace: binding}}})
