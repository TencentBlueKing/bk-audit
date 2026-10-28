"""BKBase版本及资源操作共用枚举。"""
from django.db.models import TextChoices


class BKBaseVersion(TextChoices):
    V3 = "v3", "V3"
    V4 = "v4", "V4"


class VerifiedDatasetSensitivity(TextChoices):
    """仅收录已核实可映射到审计level的Dataset字符串值。"""

    PRIVATE = "private", "私有"


class CleanRole(TextChoices):
    OWNER = "owner", "结果表创建者"
    EXISTING = "existing", "合流来源"


class CleanState(TextChoices):
    RUNNING = "Running", "运行"
    STOPPED = "Stopped", "停止"


class DorisDataModel(TextChoices):
    """已核实由插件实际使用的 Doris 表模型。"""

    DUPLICATE = "duplicate_table", "Duplicate"


BKBASE_V4_STORAGE_CLUSTER_MAP = "bkbase_v4_storage_clusters"


class TaskState(TextChoices):
    RUNNING = "running", "运行"
    STOPPED = "stopped", "停止"
    FAILED = "failed", "失败"
    PENDING = "pending", "等待"


BKBASE_V4_FLOW_CONFIG = "bkbase_v4_flow_config"

BKBASE_V4_MAX_POLLS = 60
