from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QLabel
)
from PySide6.QtCore import Qt
import logging

from .task_card import TaskCard
from ...core.task import DownloadTask

logger = logging.getLogger(__name__)

class TaskList(QWidget):
    """任务列表。"""
    
    def __init__(self, parent=None):
        """初始化任务列表。
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        self.tasks = []
        self._setup_ui()
        
    def _setup_ui(self):
        """创建界面。"""
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
            }
            QScrollArea {
                border: none;
            }
            QLabel {
                color: #999;
                font-size: 14px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 任务容器
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout()
        self.task_layout.setContentsMargins(20, 20, 20, 20)
        self.task_layout.setSpacing(20)
        self.task_layout.addStretch()
        
        # 空状态
        self.empty_label = QLabel("暂无下载任务")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.task_layout.addWidget(self.empty_label)
        
        self.task_container.setLayout(self.task_layout)
        scroll_area.setWidget(self.task_container)
        
        layout.addWidget(scroll_area)
        self.setLayout(layout)
        
    def add_task(self, task: DownloadTask):
        """添加任务。
        
        Args:
            task: 下载任务
        """
        # 创建任务卡片
        card = TaskCard(task)
        
        # 添加到列表
        self.tasks.append(task)
        self.task_layout.insertWidget(len(self.tasks) - 1, card)
        
        # 更新空状态
        self.empty_label.setVisible(not self.tasks)
        
    def remove_task(self, task: DownloadTask):
        """移除任务。
        
        Args:
            task: 下载任务
        """
        # 查找任务卡片
        for i in range(self.task_layout.count()):
            widget = self.task_layout.itemAt(i).widget()
            if isinstance(widget, TaskCard) and widget.task == task:
                # 移除卡片
                self.task_layout.removeWidget(widget)
                widget.deleteLater()
                
                # 移除任务
                self.tasks.remove(task)
                break
                
        # 更新空状态
        self.empty_label.setVisible(not self.tasks)
        
    def update_task(self, task: DownloadTask):
        """更新任务。
        
        Args:
            task: 下载任务
        """
        # 查找任务卡片
        for i in range(self.task_layout.count()):
            widget = self.task_layout.itemAt(i).widget()
            if isinstance(widget, TaskCard) and widget.task == task:
                # 更新卡片
                widget.update_task(task)
                break 