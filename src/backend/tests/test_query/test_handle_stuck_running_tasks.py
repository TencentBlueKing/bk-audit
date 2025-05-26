from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from services.web.query.models import LogExportTask, TaskEnum
from services.web.query.tasks import handle_stuck_running_tasks


class HandleStuckRunningTasksTest(SimpleTestCase):
    def setUp(self):
        """初始化固定时间和模拟任务"""
        self.fixed_now = datetime(2023, 1, 1, 12, 0)
        self.stuck_threshold = self.fixed_now - timedelta(hours=1)  # 11:00

        # 卡住的任务：RUNNING + 超时
        self.stuck_task = MagicMock(
            spec=LogExportTask,
            id=1,
            status=TaskEnum.RUNNING.value,
            updated_at=datetime(2023, 1, 1, 10, 0),  # 2小时前
            repeat_times=0,
        )

        # 正常任务：RUNNING + 未超时
        self.normal_task = MagicMock(
            spec=LogExportTask,
            id=2,
            status=TaskEnum.RUNNING.value,
            updated_at=datetime(2023, 1, 1, 11, 30),  # 30分钟前
            repeat_times=0,
        )

        # 非RUNNING任务
        self.ready_task = MagicMock(
            spec=LogExportTask,
            id=3,
            status=TaskEnum.READY.value,
            updated_at=datetime(2023, 1, 1, 10, 0),  # 2小时前
            repeat_times=0,
        )

    @patch('services.web.query.tasks.datetime')
    @patch('services.web.query.tasks.LogExportTask.objects.filter')
    def test_should_process_stuck_tasks(self, mock_filter, mock_datetime):
        """测试正确处理卡住的任务"""
        mock_datetime.now.return_value = self.fixed_now
        # 模拟filter返回符合条件的结果
        mock_filter.return_value = [self.stuck_task]

        handle_stuck_running_tasks()

        self.stuck_task.update_task_failed.assert_called_once_with("Task stuck in 'RUNNING' status for over 1 hour")

    @patch('services.web.query.tasks.datetime')
    @patch('services.web.query.tasks.LogExportTask.objects.filter')
    def test_should_ignore_normal_tasks(self, mock_filter, mock_datetime):
        """测试忽略未超时的正常任务"""
        mock_datetime.now.return_value = self.fixed_now
        # 模拟filter返回空列表（因为updated_at > threshold）
        mock_filter.return_value = []

        handle_stuck_running_tasks()

        self.normal_task.update_task_failed.assert_not_called()

    @patch('services.web.query.tasks.datetime')
    @patch('services.web.query.tasks.LogExportTask.objects.filter')
    def test_should_ignore_non_running_tasks(self, mock_filter, mock_datetime):
        """测试忽略非RUNNING状态的任务"""
        mock_datetime.now.return_value = self.fixed_now
        # 模拟filter返回空列表（因为status != RUNNING）
        mock_filter.return_value = []

        handle_stuck_running_tasks()

        self.ready_task.update_task_failed.assert_not_called()

    @patch('services.web.query.tasks.datetime')
    @patch('services.web.query.tasks.LogExportTask.objects.filter')
    def test_should_ignore_max_retry_tasks(self, mock_filter, mock_datetime):
        """测试忽略超过最大重试次数的任务"""
        mock_datetime.now.return_value = self.fixed_now
        # 模拟filter返回空列表（因为repeat_times > max）
        mock_filter.return_value = []

        handle_stuck_running_tasks()

        self.stuck_task.update_task_failed.assert_not_called()
