# -*- coding: utf-8 -*-
"""FileExporter 表头渲染单测：分类合并行文案 + 单行标题拼接。"""

from services.web.query.constants import FieldCategoryEnum, LogExportField
from services.web.query.export.file_exporter import EXTENSION_GROUP_LABEL, XLSXExporter


def _field(raw_name: str, *keys: str, display_name: str = "") -> LogExportField:
    """构造导出字段；full_key 由 cached_property 拼接，测试不直接赋。"""

    return LogExportField(raw_name=raw_name, keys=list(keys), display_name=display_name)


class TestBuildFieldTitle:
    """覆盖 _write_title_header 的单行标题拼接（原两行：显示名一行 + 字段路径一行）。

    规则（设计 10-08）：
    - 普通字段：中文显示名(英文字段路径)，如「操作起始时间(start_time)」「操作人(username)」
    - 扩展字段下钻列（full_key 形如 extend_data/{sub_key}）：只显示完整字段路径，
      display_name 是子键名本身，拼接会得到「_request_url(extend_data/_request_url)」重复语义
    - display_name 缺失或与 full_key 相同：只显示 full_key，防「start_time(start_time)」
    """

    def test_display_name_concatenated_with_full_key(self):
        field = _field("start_time", display_name="操作起始时间")
        assert XLSXExporter._build_field_title(field) == "操作起始时间(start_time)"

    def test_username_concatenated(self):
        field = _field("username", display_name="操作人")
        assert XLSXExporter._build_field_title(field) == "操作人(username)"

    def test_missing_display_name_falls_back_to_full_key(self):
        field = _field("start_time")
        assert XLSXExporter._build_field_title(field) == "start_time"

    def test_display_name_equal_full_key_not_duplicated(self):
        field = _field("start_time", display_name="start_time")
        assert XLSXExporter._build_field_title(field) == "start_time"

    def test_extension_drilldown_shows_path_only(self):
        """AI 全量平铺形态：raw_name=extend_data + keys 下钻 → 只显示完整路径"""
        field = _field("extend_data", "_request_url", display_name="_request_url")
        assert XLSXExporter._build_field_title(field) == "extend_data/_request_url"

    def test_extension_multilayer_drilldown_shows_path_only(self):
        """多层下钻：extend_data/a/b"""
        field = _field("extend_data", "a", "b", display_name="a")
        assert XLSXExporter._build_field_title(field) == "extend_data/a/b"

    def test_extension_flattened_preview_form_shows_path_only(self):
        """AI 预览平铺形态：raw_name 已是 extend_data/{key}、keys 为空 → 只显示完整路径"""
        field = _field("extend_data/_request_url", display_name="_request_url")
        assert XLSXExporter._build_field_title(field) == "extend_data/_request_url"

    def test_extension_whole_column_still_concatenated(self):
        """extend_data 整列（非下钻，full_key 无 "/"）：正常拼接中文显示名"""
        field = _field("extend_data", display_name="拓展数据")
        assert XLSXExporter._build_field_title(field) == "拓展数据(extend_data)"

    def test_non_extension_custom_field_concatenated(self):
        """检索页指定字段（自定义字段兜底分组）：正常拼接"""
        field = _field("custom_a", display_name="自定义A")
        assert XLSXExporter._build_field_title(field) == "自定义A(custom_a)"

    def test_nested_standard_field_concatenated(self):
        """标准字段多层 key（如 event_data.xx 形态）：拼接 display_name(完整路径)"""
        field = _field("event_data", "action", display_name="操作")
        assert XLSXExporter._build_field_title(field) == "操作(event_data/action)"


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


class TestCalcDisplayWidth:
    """AI 导出列宽自适应的宽度计算（近似 Excel 列宽单位）：全角/CJK 记 2，半角记 1。"""

    def test_ascii_counts_one_each(self):
        assert XLSXExporter._calc_display_width("start_time") == 10

    def test_chinese_counts_two_each(self):
        assert XLSXExporter._calc_display_width("操作起始时间") == 12

    def test_mixed_header_title(self):
        # 「操作起始时间(start_time)」= 6 中文(12) + 括号(2) + start_time(10) = 24
        assert XLSXExporter._calc_display_width("操作起始时间(start_time)") == 24

    def test_empty_string_is_zero(self):
        assert XLSXExporter._calc_display_width("") == 0
