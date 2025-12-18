from django.db import migrations

from services.web.analyze.storage_node import (
    DorisStorageNode,
    ESStorageNode,
    HDFSStorageNode,
    QueueStorageNode,
)
from services.web.strategy_v2.constants import StrategyType


def list_to_map(apps, schema_editor):
    Strategy = apps.get_model("strategy_v2", "Strategy")
    storage_node_types = [
        ESStorageNode.node_type,
        QueueStorageNode.node_type,
        HDFSStorageNode.node_type,
        DorisStorageNode.node_type,
    ]
    for strategy in Strategy.objects.filter(strategy_type=StrategyType.RULE.value):
        backend = strategy.backend_data or {}
        storage_ids = backend.get("storage_node_ids")
        if isinstance(storage_ids, list):
            print(f"Original Strategy: {strategy.pk}; storage_ids: {storage_ids}")
            mapping = {}
            for node_type, node_id in zip(storage_node_types, storage_ids):
                if node_id:
                    mapping[node_type] = node_id
            backend["storage_node_ids"] = mapping
            print(f"Updated Strategy: {strategy.pk}; storage_ids: {mapping}")
            Strategy.objects.filter(pk=strategy.pk).update(backend_data=backend)


def map_to_list(apps, schema_editor):
    Strategy = apps.get_model("strategy_v2", "Strategy")
    storage_node_types = [
        ESStorageNode.node_type,
        QueueStorageNode.node_type,
        HDFSStorageNode.node_type,
        DorisStorageNode.node_type,
    ]
    for strategy in Strategy.objects.filter(strategy_type=StrategyType.RULE.value):
        backend = strategy.backend_data or {}
        storage_ids = backend.get("storage_node_ids")
        if isinstance(storage_ids, dict):
            print(f"Original Strategy: {strategy.pk}; storage_ids: {storage_ids}")
            ordered = []
            for node_type in storage_node_types:
                node_id = storage_ids.get(node_type)
                if node_id:
                    ordered.append(node_id)
            backend["storage_node_ids"] = ordered
            print(f"Updated Strategy: {strategy.pk}; storage_ids: {ordered}")
            Strategy.objects.filter(pk=strategy.pk).update(backend_data=backend)


class Migration(migrations.Migration):
    dependencies = [
        ("strategy_v2", "0017_strategy_risk_field_config"),
    ]

    operations = [
        migrations.RunPython(list_to_map, map_to_list),
    ]
