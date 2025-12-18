import time
from typing import Dict, List, Optional

from django.conf import settings

from services.web.analyze.utils import get_service_name

__all__ = ["Event"]


class Event:
    name: str = ""  # 事件名称
    labelnames: List[str] = []  # 维度字段列表
    documentation: str = ""  # 事件说明

    # 监控平台鉴权信息
    data_id: int = settings.ALERT_DATA_ID
    access_token: str = settings.ALERT_ACCESS_TOKEN

    def __init__(self, target: str, context: Dict, extra: Optional[Dict] = None):
        self.target = target
        self.timestamp = int(time.time() * 1000)

        # 构建维度
        self.dimension = {field: str(context.get(field, "")) for field in self.labelnames}
        self.dimension["job"] = get_service_name()

        # 构建内容
        if extra:
            detail = ", ".join(f"{k}={v}" for k, v in extra.items())
            self.content = f"{self.documentation or self.name}: {detail}"
        else:
            self.content = self.documentation or self.name

    def to_json(self) -> Dict:
        return {
            "data_id": self.data_id,
            "access_token": self.access_token,
            "data": [
                {
                    "event_name": str(self.name),
                    "event": {"content": self.content},
                    "target": self.target,
                    "dimension": self.dimension,
                    "timestamp": self.timestamp,
                }
            ],
        }


class LostSceneDetectedEvent(Event):
    name = "lost_scene_detected"
    documentation = "丢失场景检测"
    labelnames = ["strategy_id", "control_id", "control_version", "strategy_name"]
