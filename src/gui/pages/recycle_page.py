"""回收站页面。"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt
import logging

from ..widgets.task_list import TaskList
from ...core.download_scheduler import DownloadScheduler
from ...core.task import TaskStatus

logger = logging.getLogger(__name__)

class RecyclePage(QWidget):
    """回收站页面。"""
    
    def __init__(self, scheduler: DownloadScheduler, parent=None):
        """初始化回收站页面。
        
        Args:
            scheduler: 下载调度器
            parent: 父窗口
        """
        super().__init__(parent)
        self.scheduler = scheduler
        self._setup_ui()
        
    def _setup_ui(self):
        """创建界面。"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 任务列表
        self.task_list = TaskList()
        layout.addWidget(self.task_list)
        
        self.setLayout(layout)
        
        # 连接信号
        self.scheduler.task_added.connect(self._on_task_added)
        self.scheduler.task_removed.connect(self._on_task_removed)
        self.scheduler.task_updated.connect(self._on_task_updated)
        
        # 加载已取消任务
        for task in self.scheduler.tasks:
            if task.status in [TaskStatus.CANCELED, TaskStatus.FAILED]:
                self.task_list.add_task(task)
        
    def _on_task_added(self, task):
        """任务添加处理。"""
        if task.status in [TaskStatus.CANCELED, TaskStatus.FAILED]:
            self.task_list.add_task(task)
        
    def _on_task_removed(self, task):
        """任务移除处理。"""
        self.task_list.remove_task(task)
        
    def _on_task_updated(self, task):
        """任务更新处理。"""
        if task.status in [TaskStatus.CANCELED, TaskStatus.FAILED]:
            if task not in self.task_list.tasks:
                self.task_list.add_task(task)
            else:
                self.task_list.update_task(task)
        else:
            if task in self.task_list.tasks:
                self.task_list.remove_task(task) 