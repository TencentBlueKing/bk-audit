"""BKBase版本及资源操作共用枚举。"""
from django.db.models import TextChoices

BKBASE_V4_NOTIFY_CHANNELS = {
    "rtx": "rtx",
    "wechat": "rtx",
    "wecom_robot": "wecom_robot",
    "wechat_group": "wecom_robot",
    "mail": "mail",
    "sms": "sms",
    "note": "sms",
    "voice": "voice",
    "phone": "voice",
}


class BKBaseVersion(TextChoices):
    V3 = "v3", "V3"
    V4 = "v4", "V4"


BKBASE_V4_REDIS_BINDING = "bkbase_v4"
BKBASE_V4_PULL_RESULTS_PATH = ".data.results"


class TableBindingKind(TextChoices):
    """已核实可作为审计 Flow 输入的 Binding 类型。"""

    CHANNEL = "ChannelBinding", "实时流水"
    REDIS = "RedisBinding", "实时关联资产"
    HDFS = "HdfsBinding", "离线存储"


class RedisRegistrationState(TextChoices):
    """仅表示本地登记/引用绑定，不代表Redis连通或任务已运行。"""

    REGISTERING = "registering", "登记已持久化"
    ACCEPTED = "accepted", "平台已受理"
    BOUND = "bound", "正式引用已保存"
    UNKNOWN = "unknown", "创建结果未知"
    REJECTED = "rejected", "创建被拒绝"


class VerifiedDatasetSensitivity(TextChoices):
    """仅收录已核实可映射到审计level的Dataset字符串值。"""

    PUBLIC = "public", "公开"
    PRIVATE = "private", "私有"
    CONFIDENTIAL = "confidential", "机密"


class CleanRole(TextChoices):
    OWNER = "owner", "结果表创建者"
    EXISTING = "existing", "合流来源"


class CleanState(TextChoices):
    RUNNING = "Running", "运行"
    STOPPED = "Stopped", "停止"


BKBASE_V4_CLEAN_TIME_FORMAT_ALIASES = {
    "yyyy-MM-dd HH:mm:ss": "%Y-%m-%d %H:%M:%S",
    "epoch_millis": "Unix Time Stamp(milliseconds)",
}


class DataSourceDesiredState(TextChoices):
    """DataSource写入使用已验证的期望态枚举。"""

    CREATED = "Created", "启动"
    STOPPED = "Stopped", "停止"


class DorisDataModel(TextChoices):
    """当前APIGW定义的Doris模型；插件和资产分别使用明细与主键模型。"""

    DUPLICATE = "duplicate_table", "Duplicate"
    PRIMARY = "primary_table", "主键模型"
    PRIMARY_PARTITION = "primary_partition_table", "主键分区模型"


BKBASE_V4_STORAGE_CLUSTER_MAP = "bkbase_v4_storage_clusters"
BKBASE_V4_STORAGE_CLUSTER_KINDS = {
    "es": "ElasticSearch",
    "doris": "Doris",
    "kafka": "Kafka",
    "hdfs": "Hdfs",
    "redis": "Redis",
}


class TaskState(TextChoices):
    RUNNING = "running", "运行"
    STOPPED = "stopped", "停止"
    FAILED = "failed", "失败"
    PENDING = "pending", "等待"


BKBASE_V4_FLOW_CONFIG = "bkbase_v4_flow_config"
BKBASE_V4_RESOURCE_NAME_MAX_LENGTH = 50
BKBASE_V4_FLOW_NODE_NAME_MAX_LENGTH = 50

# V4两条ES写入链统一使用UTC切日；V3及事件时间解析沿用原约定。
BKBASE_V4_ES_ROLLOVER_TIMEZONE = 0
BKBASE_V4_LEGACY_ES_ROLLOVER_TIMEZONE = 8

BKBASE_V4_MAX_POLLS = 60
