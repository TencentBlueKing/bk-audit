"""将部署显式提供的 Kafka/HDFS 策略写端配置一次性补入审计空间。"""
from copy import deepcopy

from blueapps.utils.logger import logger
from django.db import transaction

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from core.kms import get_secret_json
from services.web.analyze.constants import (
    DEFAULT_HDFS_STORAGE_CLUSTER_KEY,
    DEFAULT_QUEUE_STORAGE_CLUSTER_KEY,
)
from services.web.bkbase.common import (
    get_bkbase_context,
    get_bkbase_version,
    resource_params,
)
from services.web.bkbase.constants import BKBASE_V4_STORAGE_CLUSTER_MAP, BKBaseVersion
from services.web.bkbase.exceptions import BKBaseResourceMappingError

ENV_KEY = "BKAPP_INIT_STRATEGY_STORAGE_CONFIG"
STORAGE_CONFIG = {
    "kafka": (DEFAULT_QUEUE_STORAGE_CLUSTER_KEY, "Kafka"),
    "hdfs": (DEFAULT_HDFS_STORAGE_CLUSTER_KEY, "Hdfs"),
}


def _invalid(space="", field=""):
    """给出定位字段，不回显整份部署输入。"""
    return BKBaseResourceMappingError(message=f"Invalid {ENV_KEY}: space={space}, field={field}")


def _validated_entries(config):
    """写入前校验整份输入及 V4 引用作用域，不调用远端可用性接口。"""
    if not isinstance(config, dict):
        raise _invalid(field="root")
    if not config:
        return []
    v4 = get_bkbase_version() == BKBaseVersion.V4
    context = get_bkbase_context() if v4 else None
    entries = []
    for space, storages in config.items():
        if not isinstance(space, str) or not space or space != space.strip() or not isinstance(storages, dict):
            raise _invalid(field="space")
        for storage_type, value in storages.items():
            if storage_type not in STORAGE_CONFIG or not isinstance(value, dict):
                raise _invalid(space, "storage_type")
            if set(value) - {"cluster_id", "ref"}:
                raise _invalid(space, f"{storage_type}.fields")
            cluster_id = value.get("cluster_id")
            if not isinstance(cluster_id, str) or not cluster_id.strip():
                raise _invalid(space, f"{storage_type}.cluster_id")
            ref = None
            if "ref" in value:
                kind = STORAGE_CONFIG[storage_type][1]
                ref = value["ref"]
                if (
                    not v4
                    or not isinstance(ref, dict)
                    or any(
                        not isinstance(ref.get(key), str) or not ref[key].strip()
                        for key in ("kind", "tenant", "namespace", "name")
                    )
                ):
                    raise _invalid(space, f"{storage_type}.ref")
                try:
                    ref = {"kind": kind, **resource_params(context, ref, kind=kind)}
                except BKBaseResourceMappingError:
                    raise _invalid(space, f"{storage_type}.ref") from None
            entries.append((space, storage_type, cluster_id, ref))
    return entries


def _merge_ref(space, storage_type, cluster_id, ref):
    """锁住空间映射后仅补缺项，保留空值、已有引用和不可合并的运维配置。"""
    mapping, _ = GlobalMetaConfig.objects.select_for_update().get_or_create(
        config_level=ConfigLevelChoices.NAMESPACE,
        instance_key=space,
        config_key=BKBASE_V4_STORAGE_CLUSTER_MAP,
        defaults={"config_value": {}},
    )
    root = deepcopy(mapping.config_value)
    if not isinstance(root, dict) or (storage_type in root and not isinstance(root[storage_type], dict)):
        logger.warning("%s: space=%s field=%s mapping is not mergeable; preserved", ENV_KEY, space, storage_type)
        return
    refs = root.setdefault(storage_type, {})
    if cluster_id in refs:
        return
    refs[cluster_id] = ref
    mapping.config_value = root
    mapping.save(update_fields=["config_value"])


def init_strategy_storage() -> None:
    """只为显式部署输入创建缺失键，不加完成标记、不改策略运行时读取。"""
    entries = _validated_entries(get_secret_json(ENV_KEY, {}))
    if not entries:
        return
    with transaction.atomic():
        for space, storage_type, cluster_id, ref in entries:
            config, _ = GlobalMetaConfig.objects.get_or_create(
                config_level=ConfigLevelChoices.NAMESPACE,
                instance_key=space,
                config_key=STORAGE_CONFIG[storage_type][0],
                defaults={"config_value": cluster_id},
            )
            selected = config.config_value
            if (
                ref is not None
                and isinstance(selected, (str, int))
                and not isinstance(selected, bool)
                and str(selected) == cluster_id
            ):
                _merge_ref(space, storage_type, cluster_id, ref)
