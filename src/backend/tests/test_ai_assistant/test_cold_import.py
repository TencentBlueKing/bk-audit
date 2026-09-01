"""在独立进程验证 Web/Worker 不同入口，避免测试收集顺序掩盖循环导入。"""

import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


class AIAssistantColdImportTest(SimpleTestCase):
    """启动与注册不依赖数据库；每种导入顺序使用全新的模块缓存。"""

    def test_platform_entrypoints_register_business_handlers_and_tasks(self):
        """从任务、服务或 Handler 入口启动，都应完成业务注册。"""

        for entrypoint in ("tasks", "services", "handlers"):
            with self.subTest(entrypoint=entrypoint):
                code = (
                    "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings'); "
                    "from django.conf import settings; settings.LOGGING_CONFIG = None; "
                    "import django; django.setup(); "
                    f"import services.web.ai_assistant.{entrypoint}; "
                    "from services.web.ai_assistant.handlers import "
                    "message_handler_registry, attachment_handler_registry; "
                    "from services.web.ai_assistant.constants import MessageType, AttachmentType; "
                    "from blueapps.core.celery import celery_app; "
                    "assert all(message_handler_registry.require(kind) for kind in MessageType); "
                    "assert attachment_handler_registry.require(AttachmentType.AI_ANALYSIS); "
                    "assert 'ai_assistant.execute_log_analysis' in celery_app.tasks"
                )
                result = subprocess.run(
                    [sys.executable, "-c", code],
                    cwd=Path(__file__).resolve().parents[2],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
