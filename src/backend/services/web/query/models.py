from django.db import models

from core.models import OperateRecordModel


class FavoriteSearch(OperateRecordModel):
    """搜索收藏表，用于存储用户收藏的搜索条件。"""

    name = models.CharField(max_length=255)
    namespace = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    conditions = models.JSONField(help_text="The filters (conditions) for the search query.")
    sort_list = models.JSONField(help_text="Sorting options for the search query.")
    bind_system_info = models.BooleanField(default=True)

    class Meta:
        unique_together = ('name', 'created_by')

    def __str__(self):
        return f"Favorite Search by {self.created_by}: {self.name}"
