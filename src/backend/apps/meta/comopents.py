from abc import ABCMeta, abstractmethod
from typing import List, TypedDict

from django.db import transaction

from apps.meta.models import (
    EnumMappingCollection,
    EnumMappingCollectionRelation,
    EnumMappingEntity,
)


class EnumMappingAdapter(metaclass=ABCMeta):
    """
    枚举映射的适配器基类
    其他适配器类继承此类，提供实际的数据库或其他存储方式的实现
    """

    @abstractmethod
    def get_enum_mappings_by_collection_keys(self, collection_keys: List[TypedDict]) -> List[dict]:
        """根据多个 collection_id 和 key 获取对应的 name"""
        pass

    @abstractmethod
    def get_all_enum_mappings(self, collection_id: str) -> List[dict]:
        """获取指定 collection_id 下的所有枚举映射"""
        pass

    @abstractmethod
    def batch_update_enum_mappings(self, collection_id: str, batch_list: List[dict]) -> None:
        """批量更新枚举映射"""
        pass

    def add_relation(self, related_type: str, collection_id: str, related_object_id: str) -> None:
        """创建外部对象与枚举关联关系"""
        _, created = EnumMappingCollectionRelation.objects.get_or_create(
            collection_id=collection_id,
            related_type=related_type,
            related_object_id=related_object_id,
            defaults={
                'collection_id': collection_id,
                'related_type': related_type,
                'related_object_id': related_object_id,
            },
        )

    def delete_relation(self, related_type: str, collection_id: str, related_object_id: str) -> None:
        """删除外部对象与枚举关联关系"""
        EnumMappingCollectionRelation.objects.filter(
            related_type=related_type, collection_id=collection_id, related_object_id=related_object_id
        ).delete()

    def retrieve_relation(self, related_type: str, related_object_id: str) -> List[EnumMappingCollectionRelation]:
        return list(
            EnumMappingCollectionRelation.objects.filter(
                related_type=related_type, related_object_id=related_object_id
            ).all()
        )


class DBEnumMappingAdapter(EnumMappingAdapter):
    """
    数据库枚举映射适配器，操作数据库中的枚举映射数据。
    """

    def get_enum_mappings_by_collection_keys(self, collection_keys: List[TypedDict]) -> List[dict]:
        """根据多个 collection_id 和 key 获取对应的 name"""
        result = []

        for collection_key in collection_keys:
            collection_id = collection_key.get('collection_id')
            key = collection_key.get('key')

            if collection_id and key:
                collection = EnumMappingCollection.objects.get(collection_id=collection_id)
                mappings = collection.entities.filter(key=key)
                result.extend(
                    [{"collection_id": collection_id, "key": mapping.key, "name": mapping.name} for mapping in mappings]
                )

        return result

    def get_all_enum_mappings(self, collection_id: str) -> List[dict]:
        """获取指定 collection_id 下的所有枚举映射"""
        collection = EnumMappingCollection.objects.get(collection_id=collection_id)
        mappings = collection.entities.all()  # 获取所有与指定 collection_id 相关的映射
        return [{"collection_id": collection_id, "key": mapping.key, "name": mapping.name} for mapping in mappings]

    def batch_update_enum_mappings(self, collection_id: str, batch_list: List[dict]) -> None:
        """批量更新枚举映射，包括新增、更新和删除"""
        # 获取指定的枚举集合，若不存在则创建
        if not batch_list:
            EnumMappingCollection.objects.filter(collection_id=collection_id).delete()
            return
        collection, created = EnumMappingCollection.objects.get_or_create(collection_id=collection_id)

        # 获取现有的映射条目
        existing_mappings = {mapping.key: mapping for mapping in collection.entities.all()}

        # 更新或新增
        for entry in batch_list:
            key = entry.get('key')
            name = entry.get('name')

            # 如果 key 已存在，则更新
            if key in existing_mappings:
                existing_mappings[key].name = name
                existing_mappings[key].save()
            else:
                # 如果 key 不存在，新增一个枚举映射
                EnumMappingEntity.objects.create(collection=collection, key=key, name=name)

        # 删除不再存在于 batch_list 中的映射
        keys_in_batch = {entry['key'] for entry in batch_list}
        for key, mapping in existing_mappings.items():
            if key not in keys_in_batch:
                mapping.delete()

        # 删除空的 collection，如果没有任何关联的枚举实体
        if not collection.entities.exists():
            collection.delete()

    def delete_relation(self, related_type: str, collection_id: str, related_object_id: str) -> None:
        with transaction.atomic():
            super().delete_relation(related_type, collection_id, related_object_id)
            EnumMappingCollection.objects.filter(collection_id=collection_id).delete()
