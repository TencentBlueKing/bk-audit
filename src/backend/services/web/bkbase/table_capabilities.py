"""从已确认的 Binding 解析审计数据源能力。

维表语义来自 HdfsBinding 的 camelCase 配置，不能使用 DataStorage 写入参数。
能力保留多存储视角，节点按实时/离线和关联资产角色选择；Paimon仅显式true为维表。
"""
from services.web.analyze.constants import FlowDataSourceNodeType
from services.web.bkbase.constants import TableBindingKind
from services.web.bkbase.exceptions import BKBaseResourceMappingError


def parse_bindings(resource, rt_ref):
    """只投影就绪且指向本 RT 的 Binding，不保存存储连接配置。"""
    result = {"channel": False, "redis": False, "hdfs_dimensions": [], "hdfs_unknown": False}
    status = resource.get("status")
    related = status.get("related") if isinstance(status, dict) else None
    if not isinstance(related, list):
        result["hdfs_unknown"] = True
        return result
    for binding in related:
        if not isinstance(binding, dict):
            raise BKBaseResourceMappingError(message="Invalid ResultTable Binding")
        kind = binding.get("kind")
        if kind not in TableBindingKind.values:
            continue
        metadata, spec = binding.get("metadata"), binding.get("spec")
        if (
            not isinstance(metadata, dict)
            or metadata.get("tenant") != rt_ref["tenant"]
            or any(not isinstance(metadata.get(key), str) or not metadata[key] for key in ("namespace", "name"))
            or not isinstance(spec, dict)
            or spec.get("data") != rt_ref
        ):
            raise BKBaseResourceMappingError(message="Binding does not establish the selected ResultTable identity")
        state = binding.get("status")
        phase = state.get("phase") if isinstance(state, dict) else None
        if phase != "Ok":
            if kind == TableBindingKind.HDFS:
                result["hdfs_unknown"] = True
            continue
        if kind == TableBindingKind.CHANNEL:
            result["channel"] = True
        elif kind == TableBindingKind.REDIS:
            result["redis"] = True
        else:
            config = spec.get("storageConfig")
            dimensions = []
            if isinstance(config, dict):
                for engine in ("iceberg", "paimon"):
                    value = config.get(engine)
                    if isinstance(value, dict):
                        if engine == "paimon":
                            dimensions.append(value.get("dimensionTable") is True)
                        elif "dimensionTable" in value:
                            dimensions.append(value["dimensionTable"])
            if not dimensions or any(type(value) is not bool for value in dimensions) or len(set(dimensions)) != 1:
                result["hdfs_unknown"] = True
            elif dimensions[0] not in result["hdfs_dimensions"]:
                result["hdfs_dimensions"].append(dimensions[0])
    return result


def asset_status(capabilities):
    """返回资产分类 True/False/None；未知不能冒充普通流水表。"""
    dimensions = capabilities["hdfs_dimensions"]
    if capabilities["redis"] or True in dimensions:
        return True
    if capabilities["hdfs_unknown"]:
        return None
    if capabilities["channel"] or False in dimensions:
        return False
    return None


def source_node_type(capabilities, mode, *, asset=None):
    """按当前场景选节点，asset=True/False 明确指定关联资产或日志流水角色。"""
    dimensions = capabilities["hdfs_dimensions"]
    if mode == FlowDataSourceNodeType.REALTIME:
        if asset is True:
            if capabilities["redis"]:
                return FlowDataSourceNodeType.REDIS_KV_SOURCE
            return FlowDataSourceNodeType.BATCH if True in dimensions else None
        return FlowDataSourceNodeType.REALTIME if capabilities["channel"] else None
    if mode != FlowDataSourceNodeType.BATCH:
        return None
    if asset is True:
        return FlowDataSourceNodeType.BATCH if True in dimensions else None
    if asset is False:
        return FlowDataSourceNodeType.BATCH_REAL if False in dimensions else None
    if len(dimensions) == 1 and not capabilities["hdfs_unknown"]:
        return FlowDataSourceNodeType.BATCH if dimensions[0] else FlowDataSourceNodeType.BATCH_REAL
    return None
