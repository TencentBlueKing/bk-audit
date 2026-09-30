# -*- coding: utf-8 -*-
"""FileExporter 分组表头文案解析单测。"""

from services.web.query.constants import FieldCategoryEnum, LogExportField
from services.web.query.export.file_exporter import EXTENSION_GROUP_LABEL, XLSXExporter


def _field(raw_name: str, *keys: str) -> LogExportField:
    """构造导出字段；full_key 由 cached_property 拼接，测试不直接赋。"""

    return LogExportField(raw_name=raw_name, keys=list(keys))


class TestResolveCategoryLabel:
    """覆盖 _write_category_header 的分组文案解析：

    extend_data 平铺后子键列落 CUSTOM 兜底分组（不在 STANDARD/SNAPSHOT/SYSTEM
    白名单 map 内），与其他真正自定义字段共用"自定义字段"label 违背产品语义。
    仅在 AI 导出平铺场景（flatten_extension=True，AI 助手导出专属参数、检索页
    导出永不传）且 CUSTOM 分组全属 extend_data 容器系列时渲染为"扩展字段"；
    检索页导出与非平铺 AI 导出一律保持原 label，不影响既有日志检索的导出文案。
    """

    def test_non_custom_categories_preserve_label(self):
        for category in (FieldCategoryEnum.STANDARD, FieldCategoryEnum.SNAPSHOT, FieldCategoryEnum.SYSTEM):
            assert XLSXExporter._resolve_category_label(category, [_field("username")]) == category.label
            assert (
                XLSXExporter._resolve_category_label(category, [_field("username")], flatten_extension=True)
                == category.label
            )

    def test_search_page_export_keeps_custom_label(self):
        """检索页导出场景（无 flatten_extension 开关）：extend_data 子键列保持"自定义字段"。

        检索页与 AI 全量导出共用 LogExportTask + XLSXExporter 链路，label 替换
        必须以 flatten_extension 为开关隔离——检索页 export_config 永不含该键。
        """

        fields = [
            _field("extend_data", "request_url"),
            _field("extend_data", "request_data"),
        ]
        assert (
            XLSXExporter._resolve_category_label(FieldCategoryEnum.CUSTOM, fields, flatten_extension=False)
            == FieldCategoryEnum.CUSTOM.label
        )

    def test_flatten_export_with_extension_subkeys_uses_extension_label(self):
        """AI 导出平铺开启且 CUSTOM 全是子键列（full_key 形如 extend_data/{sub_key}）→ "扩展字段"。"""

        fields = [
            _field("extend_data", "request_url"),
            _field("extend_data", "request_data"),
        ]
        assert (
            XLSXExporter._resolve_category_label(FieldCategoryEnum.CUSTOM, fields, flatten_extension=True)
            == EXTENSION_GROUP_LABEL
        )

    def test_flatten_export_with_mixed_fields_keeps_custom_label(self):
        """平铺开启但 CUSTOM 混合（extend_data 子键列 + 其他兜底字段）：保守保持"自定义字段"。"""

        fields = [
            _field("extend_data", "request_url"),
            _field("other_custom"),
        ]
        assert (
            XLSXExporter._resolve_category_label(FieldCategoryEnum.CUSTOM, fields, flatten_extension=True)
            == FieldCategoryEnum.CUSTOM.label
        )

    def test_flatten_export_with_unrelated_fields_keeps_custom_label(self):
        """平铺开启但 CUSTOM 全部非 extend_data 系列（真正自定义字段）→ 保持"自定义字段"。"""

        fields = [_field("custom_a"), _field("custom_b")]
        assert (
            XLSXExporter._resolve_category_label(FieldCategoryEnum.CUSTOM, fields, flatten_extension=True)
            == FieldCategoryEnum.CUSTOM.label
        )

    def test_extension_label_is_translated_as_扩展字段(self):
        """防止后续误改 gettext 漂移：锁定 label 文本为「扩展字段」与产品语义一致。"""

        assert str(EXTENSION_GROUP_LABEL) == "扩展字段"
