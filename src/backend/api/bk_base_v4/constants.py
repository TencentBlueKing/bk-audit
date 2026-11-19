"""审计已接入的 BKBase V4 权限动作。"""
from django.db.models import TextChoices


class AuthAction(TextChoices):
    QUERY_DATASET = "query_dataset", "查询数据集"
