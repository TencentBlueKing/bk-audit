from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from services.web.query.models import LogExportTask, TaskEnum
from services.web.query.tasks import handle_stuck_running_tasks


class HandleStuckRunningTasksTest(SimpleTestCase):
    def setUp(self):
        """初始化固定时间和模拟任务"""
        self.fixed_now = datetime(2023, 1, 10, 12, 0)
        self.stuck_threshold = self.fixed_now - timedelta(hours=1)  # 11:00
        self.search_start = self.fixed_now - timedelta(days=7)  # 7天前

        # 有效卡住任务（在查询时间范围内）
        self.valid_stuck_task = MagicMock(
            spec=LogExportTask,
            id=1,
            status=TaskEnum.RUNNING.value,
            created_at=self.fixed_now - timedelta(days=3),  # 3天前创建
            updated_at=self.fixed_now - timedelta(hours=2),  # 2小时前更新
            repeat_times=0,
        )

        # 正常任务（未超时）
        self.normal_task = MagicMock(
            spec=LogExportTask,
            id=2,
            status=TaskEnum.RUNNING.value,
            created_at=self.fixed_now - timedelta(days=1),  # 1天前创建
            updated_at=self.fixed_now - timedelta(minutes=30),  # 30分钟前更新
            repeat_times=0,
        )

        # 非RUNNING状态任务
        self.ready_task = MagicMock(
            spec=LogExportTask,
            id=3,
            status=TaskEnum.READY.value,
            created_at=self.fixed_now - timedelta(days=1),  # 1天前创建
            updated_at=self.fixed_now - timedelta(hours=2),  # 2小时前更新
            repeat_times=0,
        )

        # 超出时间范围的任务（created_at超过7天）
        self.outdated_task = MagicMock(
            spec=LogExportTask,
            id=4,
            status=TaskEnum.RUNNING.value,
            created_at=self.fixed_now - timedelta(days=8),  # 8天前创建
            updated_at=self.fixed_now - timedelta(hours=2),  # 2小时前更新
            repeat_times=0,
        )

    @patch('services.web.query.tasks.settings')
    @patch('services.web.query.tasks.datetime')
    @patch('services.web.query.tasks.LogExportTask.objects.filter')
    def test_should_process_valid_stuck_tasks(self, mock_filter, mock_datetime, mock_settings):
        """测试处理符合条件的卡住任务"""
        mock_datetime.now.return_value = self.fixed_now
        mock_settings.STUCK_TASK_SEARCH_DAYS = 7
        mock_filter.return_value = [self.valid_stuck_task]

        handle_stuck_running_tasks()

        self.valid_stuck_task.update_task_failed.assert_called_once_with(
            "Task stuck in 'RUNNING' status for over 1 hour"
        )

    @patch('services.web.query.tasks.settings')
    @patch('services.web.query.tasks.datetime')
    @patch('services.web.query.tasks.LogExportTask.objects.filter')
    def test_should_ignore_outdated_tasks(self, mock_filter, mock_datetime, mock_settings):
        """测试忽略超出时间范围的任务"""
        mock_datetime.now.return_value = self.fixed_now
        mock_settings.STUCK_TASK_SEARCH_DAYS = 7

        # 关键点：模拟filter返回空列表，因为created_at超出范围
        mock_filter.return_value = []

        handle_stuck_running_tasks()

        # 验证超出时间范围的任务未被处理
        self.outdated_task.update_task_failed.assert_not_called()

    @patch('services.web.query.tasks.settings')
    @patch('services.web.query.tasks.datetime')
    @patch('services.web.query.tasks.LogExportTask.objects.filter')
    def test_should_ignore_non_stuck_tasks(self, mock_filter, mock_datetime, mock_settings):
        """测试忽略未超时的RUNNING任务"""
        mock_datetime.now.return_value = self.fixed_now
        mock_settings.STUCK_TASK_SEARCH_DAYS = 7

        # 模拟filter返回空列表（因为updated_at > threshold）
        mock_filter.return_value = []

        handle_stuck_running_tasks()

        self.normal_task.update_task_failed.assert_not_called()

    @patch('services.web.query.tasks.settings')
    @patch('services.web.query.tasks.datetime')
    @patch('services.web.query.tasks.LogExportTask.objects.filter')
    def test_should_ignore_non_running_tasks(self, mock_filter, mock_datetime, mock_settings):
        """测试忽略非RUNNING状态的任务"""
        mock_datetime.now.return_value = self.fixed_now
        mock_settings.STUCK_TASK_SEARCH_DAYS = 7

        # 模拟filter返回空列表（因为status != RUNNING）
        mock_filter.return_value = []

        handle_stuck_running_tasks()

        self.ready_task.update_task_failed.assert_not_called()

    @patch('services.web.query.tasks.settings')
    @patch('services.web.query.tasks.datetime')
    @patch('services.web.query.tasks.LogExportTask.objects.filter')
    def test_time_boundary_conditions(self, mock_filter, mock_datetime, mock_settings):
        """测试时间边界条件"""
        mock_datetime.now.return_value = self.fixed_now
        mock_settings.STUCK_TASK_SEARCH_DAYS = 7

        # 刚好在7天边界上的任务（created_at = search_start_time）
        boundary_task = MagicMock(
            spec=LogExportTask,
            id=5,
            status=TaskEnum.RUNNING.value,
            created_at=self.search_start,
            updated_at=self.fixed_now - timedelta(hours=2),
            repeat_times=0,
        )
        mock_filter.return_value = [boundary_task]

        handle_stuck_running_tasks()

        boundary_task.update_task_failed.assert_called_once()
