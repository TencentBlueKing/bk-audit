"""严格部署的声明校验与本地配置导入，不探测平台资源可用性。"""
import os
from copy import deepcopy

from django.conf import settings
from django.db import transaction

from apps.meta.constants import GLOBAL_CONFIG_LEVEL_INSTANCE, ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, Namespace
from core.kms import get_secret_json
from core.utils.distutils import strtobool
from services.web.bkbase.common import (
    get_bkbase_context,
    get_bkbase_version,
    resource_params,
)
from services.web.bkbase.constants import (
    BKBASE_V4_FLOW_CONFIG,
    BKBASE_V4_STORAGE_CLUSTER_MAP,
    BKBaseVersion,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.bkbase.flow import _new_deployment
from services.web.databus.collector.snapshot.system.provision import _create_config
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
)
from services.web.databus.storage.serializers import CreateRedisRequestSerializer
from services.web.entry.init.itsm_approval import validate_itsm_approval
from services.web.entry.init.strategy_storage import (
    ENV_KEY,
    STORAGE_CONFIG,
    _validated_entries,
)
from services.web.risk.constants import (
    EVENT_DORIS_CLUSTER_ID_KEY,
    EVENT_ES_CLUSTER_ID_KEY,
)

V4_ENV_KEY = "BKAPP_INIT_BKBASE_V4_CONFIG"
REF_KINDS = {"es": "ElasticSearch", "doris": "Doris", "kafka": "Kafka", "hdfs": "Hdfs"}


def invalid(env, space, field):
    """只暴露变量和字段位置，不回显包含凭据的声明。"""
    return BKBaseResourceMappingError(message=f"Invalid {env}: space={space}, field={field}")


class DeployStorage:
    """同一份已校验声明用于 preflight 与初始化，避免两套解释规则。"""

    def __init__(self):
        self.v4 = get_bkbase_version() == BKBaseVersion.V4
        self.strategy = get_secret_json(ENV_KEY, {})
        self.entries = _validated_entries(self.strategy)
        self.spaces = set(self.strategy) | {settings.DEFAULT_NAMESPACE}
        for space in self.spaces:
            for kind in STORAGE_CONFIG:
                if not isinstance(self.strategy.get(space, {}).get(kind), dict) or not self.strategy[space][kind]:
                    raise invalid(ENV_KEY, space, kind)
                if self.v4 and "ref" not in self.strategy[space][kind]:
                    raise invalid(ENV_KEY, space, f"{kind}.ref")
        self.es = self._storage_list("BKAPP_INIT_ES_CONFIG")
        self.doris = self._storage_list("BKAPP_INIT_DORIS_CONFIG")
        redis = get_secret_json("BKAPP_INIT_REDIS_CONFIG", [])
        if not isinstance(redis, list):
            raise invalid("BKAPP_INIT_REDIS_CONFIG", settings.DEFAULT_NAMESPACE, "root")
        # Serializer 只做本地字段校验，不建立连接或查询集群。
        serializer = CreateRedisRequestSerializer(data=redis, many=True)
        if not serializer.is_valid():
            raise invalid("BKAPP_INIT_REDIS_CONFIG", settings.DEFAULT_NAMESPACE, "redis declaration")
        self.redis = serializer.validated_data
        self._validate_redis(self.redis)
        self._validate_consumer()
        if not isinstance(settings.ASSET_RT_STORAGE_CLUSTER, str) or not settings.ASSET_RT_STORAGE_CLUSTER.strip():
            raise invalid("BKAPP_ASSET_RT_STORAGE_CLUSTER", settings.DEFAULT_NAMESPACE, "cluster_id")
        self.v4_config = get_secret_json(V4_ENV_KEY, {}) if self.v4 else {}
        if self.v4:
            self._validate_v4()
        self.approval = validate_itsm_approval()

    def _validate_redis(self, declarations):
        """Redis 只登记声明空间；快照已有显式 Ref 时无需额外的默认候选。"""
        for config in declarations:
            if config["namespace"] not in self.spaces:
                raise invalid("BKAPP_INIT_REDIS_CONFIG", config["namespace"], "namespace")
        if not self.v4:
            if not declarations:
                raise invalid("BKAPP_INIT_REDIS_CONFIG", settings.DEFAULT_NAMESPACE, "root")
            return
        kinds = ["action", "resource_type"]
        if settings.SNAPSHOT_USERINFO_RESOURCE_URL:
            kinds.append("user")
        fallback = False
        for kind in kinds:
            try:
                explicit = _create_config(kind, get_bkbase_context())
            except BKBaseResourceMappingError:
                raise invalid(
                    "BKAPP_BKBASE_V4_SYSTEM_SNAPSHOT_CREATE", settings.DEFAULT_NAMESPACE, f"{kind}.redis"
                ) from None
            fallback = fallback or explicit is None
        candidates = {
            config["redis_name_en"] for config in declarations if config["namespace"] == settings.DEFAULT_NAMESPACE
        }
        if fallback and len(candidates) != 1:
            raise invalid("BKAPP_INIT_REDIS_CONFIG", settings.DEFAULT_NAMESPACE, "unique Redis fallback candidate")

    def _storage_list(self, env):
        values = get_secret_json(env, [])
        if not isinstance(values, list) or not values:
            raise invalid(env, settings.DEFAULT_NAMESPACE, "root")
        result = {}
        for value in values:
            if not isinstance(value, dict) or not isinstance(value.get("namespace"), str):
                raise invalid(env, "", "namespace")
            space = value["namespace"]
            if space in result:
                raise invalid(env, space, "duplicate namespace")
            result[space] = value
        for space in self.spaces:
            if space not in result:
                raise invalid(env, space, "namespace")
            config = result[space]
            if env == "BKAPP_INIT_DORIS_CONFIG" or self.v4:
                if config.get("pre_defined") is not True:
                    raise invalid(env, space, "pre_defined")
                extra = config.get("pre_defined_extra_config")
                if (
                    not isinstance(extra, dict)
                    or not isinstance(extra.get("bkbase_cluster_id"), str)
                    or not extra["bkbase_cluster_id"].strip()
                ):
                    raise invalid(env, space, "pre_defined_extra_config.bkbase_cluster_id")
                if env == "BKAPP_INIT_ES_CONFIG" and (
                    type(extra.get("cluster_id")) is not int or extra["cluster_id"] <= 0
                ):
                    raise invalid(env, space, "pre_defined_extra_config.cluster_id")
        return result

    @staticmethod
    def _validate_consumer():
        env = "BKAPP_INIT_KAFKA_CONFIG"
        config = get_secret_json(env, {})
        if not isinstance(config, dict):
            raise invalid(env, "", "root")
        brokers = config.get("bootstrap_servers")
        if not (
            (isinstance(brokers, str) and brokers.strip())
            or (
                isinstance(brokers, list)
                and brokers
                and all(isinstance(item, str) and item.strip() for item in brokers)
            )
        ):
            raise invalid(env, "", "bootstrap_servers")
        if not isinstance(config.get("group_id"), str) or not config["group_id"].strip():
            raise invalid(env, "", "group_id")
        protocol = config.get("security_protocol", "PLAINTEXT")
        if protocol not in ("PLAINTEXT", "SSL", "SASL_PLAINTEXT", "SASL_SSL"):
            raise invalid(env, "", "security_protocol")
        if protocol.startswith("SASL"):
            for key in ("sasl_mechanism", "sasl_plain_username", "sasl_plain_password"):
                if not isinstance(config.get(key), str) or not config[key].strip():
                    raise invalid(env, "", key)

    def _validate_v4(self):
        context = get_bkbase_context()
        if not context["namespace"]:
            raise invalid("BKAPP_BKBASE_V4_NAMESPACE", "", "namespace")
        if not isinstance(self.v4_config, dict) or set(self.v4_config) - self.spaces:
            raise invalid(V4_ENV_KEY, "", "spaces")
        for space in self.spaces:
            config = self.v4_config.get(space, {})
            if not isinstance(config, dict) or set(config) - {"storage_refs", "flow_config"}:
                raise invalid(V4_ENV_KEY, space, "fields")
            flow = config.get("flow_config", {})
            if not isinstance(flow, dict) or not isinstance(flow.get("operation_config", {}), dict):
                raise invalid(V4_ENV_KEY, space, "flow_config.operation_config")
            refs = config.get("storage_refs", {})
            if not isinstance(refs, dict) or set(refs) - REF_KINDS.keys():
                raise invalid(V4_ENV_KEY, space, "storage_refs")
            for storage_type, mapping in refs.items():
                if not isinstance(mapping, dict):
                    raise invalid(V4_ENV_KEY, space, f"storage_refs.{storage_type}")
                for cluster_id, ref in mapping.items():
                    if (
                        not isinstance(cluster_id, str)
                        or not cluster_id.strip()
                        or not isinstance(ref, dict)
                        or any(
                            not isinstance(ref.get(key), str) or not ref[key].strip()
                            for key in ("kind", "tenant", "namespace", "name")
                        )
                    ):
                        raise invalid(V4_ENV_KEY, space, f"storage_refs.{storage_type}")
                    try:
                        resource_params(context, ref, kind=REF_KINDS[storage_type])
                    except BKBaseResourceMappingError:
                        raise invalid(V4_ENV_KEY, space, f"storage_refs.{storage_type}.{cluster_id}") from None

    def _declared_refs(self, space):
        """合并专用声明与策略写端；同一集群无需重复填写正式 Ref。"""
        declared = deepcopy(self.v4_config.get(space, {}).get("storage_refs", {}))
        for entry_space, kind, cluster_id, ref in self.entries:
            if entry_space == space and ref is not None:
                refs = declared.setdefault(kind, {})
                if cluster_id in refs and refs[cluster_id] != ref:
                    raise invalid(V4_ENV_KEY, space, f"storage_refs.{kind}.{cluster_id}")
                refs[cluster_id] = ref
        return declared

    def _check_required_refs(self, space, mapping):
        required = [
            ("es", self.es[space]["pre_defined_extra_config"]["bkbase_cluster_id"]),
            ("doris", self.doris[space]["pre_defined_extra_config"]["bkbase_cluster_id"]),
            ("hdfs", settings.ASSET_RT_STORAGE_CLUSTER),
        ]
        required.extend((kind, cluster_id) for entry_space, kind, cluster_id, _ in self.entries if entry_space == space)
        context = get_bkbase_context()
        for kind, cluster_id in required:
            refs = mapping.get(kind, {})
            ref = refs.get(cluster_id) if isinstance(refs, dict) else None
            if not isinstance(ref, dict):
                raise invalid(V4_ENV_KEY, space, f"storage_refs.{kind}.{cluster_id}")
            try:
                resource_params(context, ref, kind=REF_KINDS[kind])
            except BKBaseResourceMappingError:
                raise invalid(V4_ENV_KEY, space, f"storage_refs.{kind}.{cluster_id}") from None

    def check_first_install(self):
        """空库前校验正式存储 Ref 和内置实时 Flow 的集群，不查数据库或平台。"""
        if self.v4:
            for space in sorted(self.spaces):
                self._check_required_refs(space, self._declared_refs(space))
            space = settings.DEFAULT_NAMESPACE
            # 复用运行时的选择规则；内置策略不需要离线集群。
            _new_deployment("StreamNode", space)

    @staticmethod
    def _put(key, value, space=None):
        """锁住本地配置，只有缺记录时创建；已有空值也视作冲突。"""
        row, _ = GlobalMetaConfig.objects.select_for_update().get_or_create(
            config_key=key,
            config_level=ConfigLevelChoices.NAMESPACE if space is not None else ConfigLevelChoices.GLOBAL,
            instance_key=space if space is not None else GLOBAL_CONFIG_LEVEL_INSTANCE,
            defaults={"config_value": value},
        )
        if row.config_value != value:
            raise invalid(V4_ENV_KEY, space or "", key)

    def apply(self):
        """先对照所有本地登记，再原子补缺，任一冲突不会留半套配置。"""
        actual_spaces = set(Namespace.objects.values_list("namespace", flat=True))
        if missing := actual_spaces - self.spaces:
            raise invalid(ENV_KEY, sorted(missing)[0], "kafka/hdfs declaration")
        with transaction.atomic():
            for space in sorted(self.spaces):
                Namespace.objects.get_or_create(namespace=space, defaults={"name": space})
                for entry_space, kind, cluster_id, _ in self.entries:
                    if entry_space == space:
                        self._put(STORAGE_CONFIG[kind][0], cluster_id, space)
                if not self.v4:
                    # V3 存储创建和激活仍交给原资源入口。
                    continue
                es_extra = self.es[space]["pre_defined_extra_config"]
                doris_extra = self.doris[space]["pre_defined_extra_config"]
                row, _ = GlobalMetaConfig.objects.select_for_update().get_or_create(
                    config_key=BKBASE_V4_STORAGE_CLUSTER_MAP,
                    config_level=ConfigLevelChoices.NAMESPACE,
                    instance_key=space,
                    defaults={"config_value": {}},
                )
                mapping = deepcopy(row.config_value)
                if not isinstance(mapping, dict):
                    raise invalid(V4_ENV_KEY, space, "storage_refs")
                for kind, refs in self._declared_refs(space).items():
                    saved = mapping.setdefault(kind, {})
                    if not isinstance(saved, dict):
                        raise invalid(V4_ENV_KEY, space, f"storage_refs.{kind}")
                    for cluster_id, ref in refs.items():
                        if cluster_id in saved:
                            if not isinstance(saved[cluster_id], dict) or any(
                                saved[cluster_id].get(key) != ref.get(key)
                                for key in ("kind", "tenant", "namespace", "name")
                            ):
                                raise invalid(V4_ENV_KEY, space, f"storage_refs.{kind}.{cluster_id}")
                        else:
                            saved[cluster_id] = ref
                self._check_required_refs(space, mapping)
                row.config_value = mapping
                row.save(update_fields=["config_value"])
                if profile := self.v4_config.get(space, {}).get("flow_config"):
                    self._put(BKBASE_V4_FLOW_CONFIG, profile, space)
                self._put(DEFAULT_STORAGE_CONFIG_KEY, es_extra["cluster_id"], space)
                self._put(DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY, doris_extra, space)
            if self.v4:
                default = settings.DEFAULT_NAMESPACE
                self._put(EVENT_ES_CLUSTER_ID_KEY, self.es[default]["pre_defined_extra_config"]["cluster_id"])
                self._put(
                    EVENT_DORIS_CLUSTER_ID_KEY, self.doris[default]["pre_defined_extra_config"]["bkbase_cluster_id"]
                )


def validate_deployment():
    """迁移前仅校验声明；是否启用 init 也是严格入口的显式合同。"""
    if not strtobool(os.getenv("BKAPP_INIT_SYSTEM", "False")):
        raise invalid("BKAPP_INIT_SYSTEM", "", "enabled")
    return DeployStorage()
