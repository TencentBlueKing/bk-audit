import json

from django.db import migrations

FIELD_PAIRS = [
    ("operator", "operator_str"),
    ("current_operator", "current_operator_str"),
    ("notice_users", "notice_users_str"),
]


def _ensure_list(value):
    """将 JSONField 的值统一为 Python list（兼容 str / list / None）"""
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if v]


def forwards(apps, schema_editor):
    Risk = apps.get_model("risk", "Risk")

    batch_size = 2000
    queryset = Risk.objects.all().order_by("pk")
    total = queryset.count()
    if total == 0:
        return

    start = 0
    while start < total:
        batch = list(queryset[start : start + batch_size])
        updates = []
        for obj in batch:
            changed = False
            for json_field, str_field in FIELD_PAIRS:
                json_val = getattr(obj, json_field)
                new_val = _ensure_list(json_val)
                if getattr(obj, str_field) != new_val:
                    setattr(obj, str_field, new_val)
                    changed = True
            if changed:
                updates.append(obj)
        if updates:
            Risk.objects.bulk_update(updates, [f for _, f in FIELD_PAIRS], batch_size=batch_size)
        start += batch_size


def backwards(apps, schema_editor):
    Risk = apps.get_model("risk", "Risk")

    batch_size = 2000
    queryset = Risk.objects.all().order_by("pk")
    total = queryset.count()
    if total == 0:
        return

    start = 0
    while start < total:
        batch = list(queryset[start : start + batch_size])
        updates = []
        for obj in batch:
            changed = False
            for json_field, str_field in FIELD_PAIRS:
                str_val = getattr(obj, str_field)
                new_val = str_val if isinstance(str_val, list) else []
                if getattr(obj, json_field) != new_val:
                    setattr(obj, json_field, new_val)
                    changed = True
            if changed:
                updates.append(obj)
        if updates:
            Risk.objects.bulk_update(updates, [f for f, _ in FIELD_PAIRS], batch_size=batch_size)
        start += batch_size


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0045_add_multi_str_split_fields"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
