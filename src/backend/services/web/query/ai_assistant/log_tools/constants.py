"""日志工具共享的稳定协议枚举。

枚举值保持既有请求与响应协议不变，中文 label 供后台、文档和诊断使用。
Pydantic Schema 从本模块导入这些 Choices，并保留原有导入路径。
"""

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy


class LogFieldType(TextChoices):
    """日志检索可见字段的存储类型，兼容 BKBase JSON 与索引字段类型。"""

    STRING = "string", gettext_lazy("字符串")
    DOUBLE = "double", gettext_lazy("双精度浮点数")
    INT = "int", gettext_lazy("整数")
    LONG = "long", gettext_lazy("长整数")
    TEXT = "text", gettext_lazy("文本")
    TIMESTAMP = "timestamp", gettext_lazy("时间戳")
    FLOAT = "float", gettext_lazy("单精度浮点数")
    OBJECT = "object", gettext_lazy("对象")
    NESTED = "nested", gettext_lazy("嵌套对象")
    KEYWORD = "keyword", gettext_lazy("关键字")


class LogFieldCategory(TextChoices):
    """字段探索响应分类，不返回请求专用的 ALL。"""

    BASIC = "BASIC", gettext_lazy("基础字段")
    EXTENDED = "EXTENDED", gettext_lazy("拓展字段")


class LogFieldMetadataTypeSource(TextChoices):
    """字段类型的来源，避免把采样观察误表述为全量定义。"""

    DECLARED = "DECLARED", gettext_lazy("字段声明")
    INFERRED = "INFERRED", gettext_lazy("样本推断")


class JSONValueType(TextChoices):
    """JSON 样本中的值类型，避免调用方解释任意类型字符串。"""

    BOOLEAN = "boolean", gettext_lazy("布尔值")
    INTEGER = "integer", gettext_lazy("整数")
    NUMBER = "number", gettext_lazy("数值")
    STRING = "string", gettext_lazy("字符串")
    ARRAY = "array", gettext_lazy("数组")
    OBJECT = "object", gettext_lazy("对象")
    NULL = "null", gettext_lazy("空值")


class LogSortDirection(TextChoices):
    """日志明细排序方向。"""

    ASC = "asc", gettext_lazy("升序")
    DESC = "desc", gettext_lazy("降序")


class StatisticsKind(TextChoices):
    """字段可使用的统计包类型。"""

    CATEGORICAL = "CATEGORICAL", gettext_lazy("类别统计")
    NUMERIC = "NUMERIC", gettext_lazy("数值统计")


class StatisticsUnsupportedReason(TextChoices):
    """字段目录不可直接统计的稳定原因，不披露敏感规则。"""

    OBJECT = "OBJECT", gettext_lazy("对象类型不可统计")
    ARRAY = "ARRAY", gettext_lazy("数组类型不可统计")
    UNKNOWN_TYPE = "UNKNOWN_TYPE", gettext_lazy("字段类型未知")
    PERMISSION_DENIED = "PERMISSION_DENIED", gettext_lazy("无字段权限")


class AggregationMetricType(TextChoices):
    """聚合函数枚举，禁止接收调用方给出的函数名。"""

    COUNT = "COUNT", gettext_lazy("计数")
    DISTINCT_COUNT = "DISTINCT_COUNT", gettext_lazy("去重计数")
    MIN = "MIN", gettext_lazy("最小值")
    MAX = "MAX", gettext_lazy("最大值")
    AVG = "AVG", gettext_lazy("平均值")
    SUM = "SUM", gettext_lazy("求和")
    PERCENTILE_APPROX = "PERCENTILE_APPROX", gettext_lazy("近似百分位数")


class AggregationDimensionType(TextChoices):
    """聚合维度只允许字段或受控时间桶。"""

    FIELD = "FIELD", gettext_lazy("字段维度")
    TIME_BUCKET = "TIME_BUCKET", gettext_lazy("时间桶维度")


class AggregationValueType(TextChoices):
    """字符串或拓展数值转换的固定 Doris 目标类型。"""

    LONG = "LONG", gettext_lazy("长整数")
    DOUBLE = "DOUBLE", gettext_lazy("双精度浮点数")


class AggregationTimeInterval(TextChoices):
    """时间桶粒度；AUTO 只存在于请求阶段。"""

    AUTO = "AUTO", gettext_lazy("自动选择")
    MINUTE = "MINUTE", gettext_lazy("分钟")
    HOUR = "HOUR", gettext_lazy("小时")
    DAY = "DAY", gettext_lazy("天")


class AggregationEffectiveTimeInterval(TextChoices):
    """聚合响应中的实际时间桶粒度，不含请求专用的 AUTO。"""

    MINUTE = "MINUTE", gettext_lazy("分钟")
    HOUR = "HOUR", gettext_lazy("小时")
    DAY = "DAY", gettext_lazy("天")


class AggregationOrderDirection(TextChoices):
    """排序方向固定为 Doris 可映射的两个枚举值。"""

    ASC = "ASC", gettext_lazy("升序")
    DESC = "DESC", gettext_lazy("降序")


class AggregationColumnRole(TextChoices):
    """聚合响应列的语义角色。"""

    DIMENSION = "DIMENSION", gettext_lazy("维度列")
    METRIC = "METRIC", gettext_lazy("指标列")


class AggregationResultDataType(TextChoices):
    """聚合列对外声明的数据类型。"""

    STRING = "string", gettext_lazy("字符串")
    DOUBLE = "double", gettext_lazy("双精度浮点数")
    INT = "int", gettext_lazy("整数")
    LONG = "long", gettext_lazy("长整数")
    TEXT = "text", gettext_lazy("文本")
    TIMESTAMP = "timestamp", gettext_lazy("时间戳")
    FLOAT = "float", gettext_lazy("单精度浮点数")
    DATETIME = "datetime", gettext_lazy("日期时间")
    BOOLEAN = "boolean", gettext_lazy("布尔值")
    NUMBER = "number", gettext_lazy("数值")
    SCALAR = "scalar", gettext_lazy("标量")


class AggregationGroupKind(TextChoices):
    """完整聚合的真实类别与合成分组。"""

    VALUE = "VALUE", gettext_lazy("真实类别")
    OTHER = "OTHER", gettext_lazy("其他类别")
    MISSING = "MISSING", gettext_lazy("缺失值")
    ALL = "ALL", gettext_lazy("全量汇总")
