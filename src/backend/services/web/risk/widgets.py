import json
from typing import Any

from django import forms


class WhereConditionWidget(forms.Widget):
    template_name = "admin/risk/widgets/where_condition.html"

    def __init__(
        self,
        field_options: list[dict[str, Any]],
        operator_options: list[tuple[str, str]],
        field_type_options: list[tuple[str, str]] | None = None,
        attrs=None,
    ):
        self.field_options = [
            {
                **option,
                "label": str(option.get("label") or option.get("name") or option.get("raw_name")),
                "category_display": str(option.get("category_display") or option.get("category")),
            }
            for option in field_options
        ]
        self.operator_options = [(value, str(label)) for value, label in operator_options]
        self.field_type_options = [(value, str(label)) for value, label in (field_type_options or [])]
        super().__init__(attrs)

    def format_value(self, value):
        if value in (None, "", {}):
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, indent=2)

    def value_from_datadict(self, data, files, name):
        raw = data.get(name)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return raw

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        widget_attrs = widget.get("attrs") or {}
        if "id" not in widget_attrs:
            widget_attrs["id"] = f"id_{name}"
        widget["attrs"] = widget_attrs
        field_options_id = f'{widget_attrs["id"]}-field-options'
        operator_options_id = f'{widget_attrs["id"]}-operator-options'
        field_type_options_id = f'{widget_attrs["id"]}-field-type-options'
        context["widget"].update(
            {
                "field_options_json": json.dumps(self.field_options, ensure_ascii=False),
                "operator_options_json": json.dumps(self.operator_options, ensure_ascii=False),
                "field_type_options_json": json.dumps(self.field_type_options, ensure_ascii=False),
                "field_options_id": field_options_id,
                "operator_options_id": operator_options_id,
                "field_type_options_id": field_type_options_id,
                "value": self.format_value(value) or "",
            }
        )
        return context

    class Media:
        js = ["risk/js/where_condition_widget.js"]
        css = {"all": ["risk/css/where_condition_widget.css"]}
