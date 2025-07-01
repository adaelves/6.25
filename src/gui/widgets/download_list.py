"""下载列表组件模块。

提供下载任务的显示和管理功能。
"""

from typing import Optional, List, Dict, Any
import logging
from pathlib import Path
import os

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMenu,
    QMessageBox,
    QProgressBar,
    QStyledItemDelegate,
    QScrollArea,
    QFrame,
    QLabel,
    QHBoxLayout,
    QButtonGroup,
    QPushButton,
    QListWidget,
    QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction, QColor, QPainter, QBrush

from ...core.download_task import DownloadTask, TaskStatus
from .task_card import TaskCard

logger = logging.getLogger(__name__)

class ProgressBarDelegate(QStyledItemDelegate):
    """进度条代理。
    
    在表格单元格中显示进度条。
    """
    
    def paint(self, painter: QPainter, option, index):
        """绘制进度条。
        
        Args:
            painter: 画笔
            option: 样式选项
            index: 单元格索引
        """
        progress = index.data(Qt.DisplayRole)
        if not isinstance(progress, (int, float)):
            return super().paint(painter, option, index)
            
        # 创建进度条
        progress_bar = QProgressBar()
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        progress_bar.setValue(int(progress * 100))
        progress_bar.setTextVisible(True)
        progress_bar.setFormat(f"{progress * 100:.1f}%")
        
        # 设置进度条大小
        progress_bar.setGeometry(option.rect)
        
        # 保存画笔状态
        painter.save()
        
        # 绘制进度条
        progress_bar.render(
            painter,
            option.rect.topLeft(),
            renderFlags=QWidget.DrawChildren
        )
        
        # 恢复画笔状态
        painter.restore()

class DownloadList(QWidget):
    """下载任务列表。
    
    显示所有下载任务，包括正在下载、已完成和失败的任务。
    支持任务状态过滤和分类显示。
    """
    
    # 信号定义
    task_paused = Signal(str)  # 任务ID
    task_resumed = Signal(str)  # 任务ID
    task_removed = Signal(str)  # 任务ID
    task_retried = Signal(str)  # 任务ID
    open_file = Signal(str)    # 文件路径
    open_folder = Signal(str)  # 文件夹路径
    
    def __init__(self, parent=None):
        """初始化下载列表。"""
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        """创建界面。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 过滤栏
        filter_bar = QWidget()
        filter_bar.setStyleSheet("""
            QWidget {
                background-color: white;
                border-bottom: 1px solid #e8e8e8;
            }
        """)
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(20, 10, 20, 10)
        
        # 状态过滤按钮组
        self.status_group = QButtonGroup(self)
        self.status_group.setExclusive(True)
        
        # 全部
        all_btn = QPushButton("全部")
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.setProperty("status", None)
        
        # 正在下载
        downloading_btn = QPushButton("正在下载")
        downloading_btn.setCheckable(True)
        downloading_btn.setProperty("status", TaskStatus.DOWNLOADING)
        
        # 已完成
        completed_btn = QPushButton("已完成")
        completed_btn.setCheckable(True)
        completed_btn.setProperty("status", TaskStatus.COMPLETED)
        
        # 已暂停
        paused_btn = QPushButton("已暂停")
        paused_btn.setCheckable(True)
        paused_btn.setProperty("status", TaskStatus.PAUSED)
        
        # 失败
        failed_btn = QPushButton("失败")
        failed_btn.setCheckable(True)
        failed_btn.setProperty("status", TaskStatus.FAILED)
        
        # 添加按钮到按钮组
        for btn in [all_btn, downloading_btn, completed_btn, paused_btn, failed_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #666;
                    border: none;
                    padding: 8px 16px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    color: #1890ff;
                }
                QPushButton:checked {
                    color: #1890ff;
                    font-weight: bold;
                    border-bottom: 2px solid #1890ff;
                }
            """)
            self.status_group.addButton(btn)
            filter_layout.addWidget(btn)
            
        filter_layout.addStretch()
        layout.addWidget(filter_bar)
        
        # 任务列表
        self.task_list = QListWidget()
        self.task_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
            }
            QListWidget::item {
                background-color: white;
                margin: 5px 0;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        layout.addWidget(self.task_list)
        
        # 连接信号
        self.status_group.buttonClicked.connect(self._filter_tasks)
        
    def add_task(self, task: DownloadTask):
        """添加任务到列表。
        
        Args:
            task: 下载任务
        """
        # 创建任务卡片
        card = TaskCard(task)
        card.pause_clicked.connect(lambda: self.task_paused.emit(task.id))
        card.resume_clicked.connect(lambda: self.task_resumed.emit(task.id))
        card.remove_clicked.connect(lambda: self.task_removed.emit(task.id))
        card.retry_clicked.connect(lambda: self.task_retried.emit(task.id))
        card.open_file_clicked.connect(lambda: self.open_file.emit(str(task.save_path)))
        card.open_folder_clicked.connect(lambda: self.open_folder.emit(str(task.save_path.parent)))
        
        # 创建列表项
        item = QListWidgetItem()
        item.setSizeHint(card.sizeHint())
        item.setData(Qt.UserRole, task)
        
        # 添加到列表
        self.task_list.addItem(item)
        self.task_list.setItemWidget(item, card)
        
        # 应用过滤
        self._filter_tasks()
        
    def update_task(self, task: DownloadTask):
        """更新任务状态。
        
        Args:
            task: 下载任务
        """
        # 查找任务项
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item.data(Qt.UserRole).id == task.id:
                # 更新任务卡片
                card = self.task_list.itemWidget(item)
                card.update_task(task)
                
                # 更新过滤
                self._filter_tasks()
                break
                
    def remove_task(self, task_id: str):
        """移除任务。
        
        Args:
            task_id: 任务ID
        """
        # 查找并移除任务项
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item.data(Qt.UserRole).id == task_id:
                self.task_list.takeItem(i)
                break
                
    def _filter_tasks(self):
        """根据状态过滤任务。"""
        # 获取选中的状态
        btn = self.status_group.checkedButton()
        status = btn.property("status") if btn else None
        
        # 遍历所有任务
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            task = item.data(Qt.UserRole)
            
            # 根据状态显示/隐藏
            if status is None or task.status == status:
                item.setHidden(False)
            else:
                item.setHidden(True)
        
    def _show_context_menu(self, pos):
        """显示右键菜单。
        
        Args:
            pos: 菜单位置
        """
        task = self.get_selected_task()
        if not task:
            return
            
        try:
            menu = QMenu(self)
            
            # 打开文件
            if task.status == TaskStatus.COMPLETED:
                open_file = QAction("打开文件", self)
                open_file.triggered.connect(
                    lambda: self.open_file.emit(task.save_path)
                )
                menu.addAction(open_file)
                
                open_folder = QAction("打开目录", self)
                open_folder.triggered.connect(
                    lambda: self.open_folder.emit(task.save_path.parent)
                )
                menu.addAction(open_folder)
                
                menu.addSeparator()
                
            # 暂停/继续
            if task.status == TaskStatus.DOWNLOADING:
                pause = QAction("暂停", self)
                pause.triggered.connect(
                    lambda: self.task_paused.emit(task.id)
                )
                menu.addAction(pause)
            elif task.status == TaskStatus.PAUSED:
                resume = QAction("继续", self)
                resume.triggered.connect(
                    lambda: self.task_resumed.emit(task.id)
                )
                menu.addAction(resume)
                
            # 重试
            if task.status in (TaskStatus.FAILED, TaskStatus.CANCELED):
                retry = QAction("重试", self)
                retry.triggered.connect(
                    lambda: self.task_retried.emit(task.id)
                )
                menu.addAction(retry)
                
            # 删除
            menu.addSeparator()
            delete = QAction("删除", self)
            delete.triggered.connect(
                lambda: self._confirm_delete_task(task)
            )
            menu.addAction(delete)
            
            # 显示菜单
            menu.exec(self.task_list.viewport().mapToGlobal(pos))
            
        except Exception as e:
            logger.error(f"显示右键菜单失败: {e}")
            
    def _confirm_delete_task(self, task: DownloadTask):
        """确认删除任务。
        
        Args:
            task: 要删除的任务
        """
        try:
            # 确认是否删除文件
            if task.status == TaskStatus.COMPLETED and task.save_path.exists():
                reply = QMessageBox.question(
                    self,
                    "确认删除",
                    "是否同时删除已下载的文件？",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                
                if reply == QMessageBox.Cancel:
                    return
                    
                # 删除文件
                if reply == QMessageBox.Yes:
                    try:
                        task.save_path.unlink()
                    except Exception as e:
                        logger.error(f"删除文件失败: {e}")
                        QMessageBox.warning(
                            self,
                            "错误",
                            f"删除文件失败: {e}"
                        )
                        
            # 发送删除信号
            self.task_removed.emit(task.id)
            
        except Exception as e:
            logger.error(f"删除任务失败: {e}")
            QMessageBox.warning(
                self,
                "错误",
                f"删除任务失败: {e}"
            )
            
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
            
    @staticmethod
    def _format_time(seconds: int) -> str:
        """格式化时间显示。
        
        Args:
            seconds: 剩余秒数
            
        Returns:
            str: 格式化后的时间字符串
        """
        if seconds < 0:
            return "--:--"
        elif seconds < 60:
            return f"00:{seconds:02d}"
        elif seconds < 3600:
            return f"{seconds//60:02d}:{seconds%60:02d}"
        else:
            return f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}" 