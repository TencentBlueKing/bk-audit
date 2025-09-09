from __future__ import annotations

from django.db import models


class CallerResourceType(models.TextChoices):
    RISK = "risk"
