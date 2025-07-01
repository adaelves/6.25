"""任务卡片组件。

提供现代化的任务显示界面。
"""

from typing import Optional
from pathlib import Path
from datetime import datetime
import humanize
import logging

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QMenu,
    QToolButton,
    QFrame,
    QSizePolicy
)
from PySide6.QtCore import (
    Qt,
    Signal,
    QSize,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    Property
)
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QLinearGradient,
    QPalette,
    QIcon,
    QFontMetrics
)

from ...core.download_task import DownloadTask, TaskStatus

logger = logging.getLogger(__name__)

class ModernProgressBar(QProgressBar):
    """现代风格进度条。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setFixedHeight(4)
        
    def paintEvent(self, event):
        """自定义绘制进度条。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#f0f0f0"))
        painter.drawRoundedRect(self.rect(), 2, 2)
        
        # 计算进度宽度
        progress = self.value() / (self.maximum() or 100)
        progress_width = int(self.width() * progress)
        
        if progress_width > 0:
            # 创建渐变色
            gradient = QLinearGradient(0, 0, self.width(), 0)
            gradient.setColorAt(0, QColor("#1890ff"))
            gradient.setColorAt(1, QColor("#52c41a"))
            
            # 绘制进度
            painter.setBrush(gradient)
            painter.drawRoundedRect(0, 0, progress_width, self.height(), 2, 2)

class TaskCard(QWidget):
    """任务卡片组件。
    
    显示单个下载任务的信息和控制按钮。
    使用类似 youtube-dl-gui 的现代卡片式设计。
    """
    
    # 信号定义
    pause_clicked = Signal()
    resume_clicked = Signal()
    remove_clicked = Signal()
    retry_clicked = Signal()
    open_file_clicked = Signal()
    open_folder_clicked = Signal()
    
    def __init__(self, task: DownloadTask, parent=None):
        """初始化任务卡片。
        
        Args:
            task: 下载任务
            parent: 父组件
        """
        super().__init__(parent)
        self.task = task
        self._setup_ui()
        self.update_task(task)
        
    def _setup_ui(self):
        """创建界面。"""
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 8px;
            }
            QLabel {
                color: #333;
            }
            QPushButton {
                padding: 5px 10px;
                border: none;
                border-radius: 4px;
                background-color: #1890ff;
                color: white;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
            QPushButton:pressed {
                background-color: #096dd9;
            }
            QPushButton[flat=true] {
                background-color: transparent;
                color: #1890ff;
            }
            QPushButton[flat=true]:hover {
                color: #40a9ff;
            }
            QProgressBar {
                border: none;
                background-color: #f5f5f5;
                height: 4px;
            }
            QProgressBar::chunk {
                background-color: #1890ff;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # 顶部信息
        top_layout = QHBoxLayout()
        
        # 缩略图
        self.thumbnail = QLabel()
        self.thumbnail.setFixedSize(120, 68)
        self.thumbnail.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border-radius: 4px;
            }
        """)
        top_layout.addWidget(self.thumbnail)
        
        # 右侧信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        # 标题栏
        title_layout = QHBoxLayout()
        
        # 平台图标
        platform_icon = QLabel()
        platform_icon.setFixedSize(24, 24)
        platform_icon.setPixmap(self._get_platform_icon())
        
        # 标题
        self.title_label = QLabel()
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
            }
        """)
        
        # 状态
        self.status_label = QLabel()
        self.status_label.setStyleSheet("""
            QLabel {
                color: #999;
            }
        """)
        
        title_layout.addWidget(platform_icon)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.status_label)
        
        info_layout.addLayout(title_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        
        # 底部栏
        bottom_layout = QHBoxLayout()
        
        # 进度信息
        progress_layout = QHBoxLayout()
        
        self.size_label = QLabel()
        self.size_label.setStyleSheet("color: #666;")
        progress_layout.addWidget(self.size_label)
        
        progress_layout.addWidget(self.progress_bar)
        
        info_layout.addLayout(progress_layout)
        
        # 速度
        self.speed_label = QLabel()
        self.speed_label.setStyleSheet("""
            QLabel {
                color: #999;
            }
        """)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(self._on_pause)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setFlat(True)
        self.cancel_btn.clicked.connect(self._on_cancel)
        
        button_layout.addWidget(self.pause_btn)
        button_layout.addWidget(self.cancel_btn)
        
        bottom_layout.addWidget(self.speed_label)
        bottom_layout.addStretch()
        bottom_layout.addLayout(button_layout)
        
        # 添加到主布局
        info_layout.addLayout(bottom_layout)
        
        top_layout.addLayout(info_layout)
        layout.addLayout(top_layout)
        
    def _get_platform_icon(self):
        """获取平台图标。"""
        platform_icons = {
            'youtube': 'resources/icons/youtube.svg',
            'twitter': 'resources/icons/twitter.svg',
            'bilibili': 'resources/icons/bilibili.svg'
        }
        
        icon_path = platform_icons.get(self.task.platform, 'resources/icons/unknown.svg')
        return QIcon(icon_path).pixmap(24, 24)
        
    def update_task(self, task: DownloadTask):
        """更新任务信息。
        
        Args:
            task: 下载任务
        """
        self.task = task
        
        # 更新标题
        self.title_label.setText(task.title or task.url)
        
        # 更新进度
        self.progress_bar.setValue(int(task.progress * 100))
        
        # 更新大小信息
        if task.total_size > 0:
            downloaded = self._format_size(task.downloaded_size)
            total = self._format_size(task.total_size)
            self.size_label.setText(f"{downloaded} / {total}")
        else:
            self.size_label.setText("-")
            
        # 更新状态
        self.status_label.setText(task.status.value)
        
        # 更新速度
        if task.status == TaskStatus.DOWNLOADING:
            speed = self._format_speed(task.download_speed)
            self.speed_label.setText(speed)
        else:
            self.speed_label.clear()
            
        # 更新按钮状态
        self._update_buttons()
        
    def _update_buttons(self):
        """更新按钮状态。"""
        # 暂停/继续按钮
        if self.task.status == TaskStatus.DOWNLOADING:
            self.pause_btn.setText("继续")
            self.pause_btn.clicked.connect(self.resume_clicked)
            self.cancel_btn.setEnabled(True)
        elif self.task.status == TaskStatus.PAUSED:
            self.pause_btn.setText("暂停")
            self.pause_btn.clicked.connect(self.pause_clicked)
            self.cancel_btn.setEnabled(True)
        else:
            self.pause_btn.setText("暂停")
            self.pause_btn.clicked.connect(self.pause_clicked)
            self.cancel_btn.setEnabled(False)
            
        # 重试按钮
        self.retry_btn.setVisible(self.task.status == TaskStatus.FAILED)
        
        # 打开文件按钮
        self.open_file_btn.setVisible(self.task.status == TaskStatus.COMPLETED)
        
    @staticmethod
    def _format_size(size: int) -> str:
        """格式化文件大小。
        
        Args:
            size: 文件大小(bytes)
            
        Returns:
            str: 格式化后的大小
        """
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size/1024/1024:.1f} MB"
        else:
            return f"{size/1024/1024/1024:.1f} GB"
            
    @staticmethod
    def _format_speed(speed: float) -> str:
        """格式化下载速度。
        
        Args:
            speed: 下载速度(bytes/s)
            
        Returns:
            str: 格式化后的速度
        """
        if speed < 1024:
            return f"{speed:.1f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed/1024:.1f} KB/s"
        elif speed < 1024 * 1024 * 1024:
            return f"{speed/1024/1024:.1f} MB/s"
        else:
            return f"{speed/1024/1024/1024:.1f} GB/s"
        
    def _on_pause(self):
        """暂停/继续下载。"""
        try:
            if self.task.status == TaskStatus.DOWNLOADING:
                self.task.pause()
            elif self.task.status == TaskStatus.PAUSED:
                self.task.resume()
                
            self.update_task(self.task)
            
        except Exception as e:
            logger.error(f"暂停/继续下载失败: {e}")
            
    def _on_cancel(self):
        """取消下载。"""
        try:
            self.task.cancel()
            self.update_task(self.task)
            
        except Exception as e:
            logger.error(f"取消下载失败: {e}") 