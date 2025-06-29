#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频下载器主窗口模块。

实现主要的GUI界面和交互逻辑。
"""

import sys
import os
import asyncio
from asyncio import AbstractEventLoop
from concurrent.futures import ThreadPoolExecutor

# 添加项目根目录到 Python 路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
from queue import Queue
import json

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QProgressBar,
    QLabel,
    QFileDialog,
    QMessageBox,
    QDialog,
    QFormLayout,
    QComboBox,
    QMenuBar,
    QMenu,
    QStatusBar,
    QApplication,
    QSystemTrayIcon,
    QStyle,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView
)
from PySide6.QtCore import Qt, Slot, Signal, QTimer, QThread, QSettings
from PySide6.QtGui import QIcon, QPalette, QColor, QAction

from src.core.downloader import BaseDownloader
from src.utils.logger import get_logger
from src.plugins.youtube.downloader import YouTubeDownloader
from src.plugins.youtube.config import YouTubeDownloaderConfig
from src.plugins.twitter.downloader import TwitterDownloader
from src.plugins.twitter.config import TwitterDownloaderConfig
from src.utils.cookie_manager import CookieManager
from src.gui.cookie_dialog import CookieDialog
from src.plugins.pornhub.downloader import PornhubDownloader
from src.plugins.pornhub.config import PornhubDownloaderConfig
from src.core.exceptions import DownloadError
from src.utils.config import ConfigManager
from src.gui.dialogs.help_dialog import HelpDialog
from src.gui.dialogs.settings_dialog import SettingsDialog
from src.gui.dialogs.add_task_dialog import AddTaskDialog
from src.core.download_scheduler import DownloadScheduler
from src.core.exceptions import DownloaderError
from .theme import ThemeManager, load_style
from .download_dialog import DownloadDialog
from .settings_dialog import SettingsDialog
from .help_dialog import HelpDialog
from ..core.download_scheduler import DownloadScheduler
from ..core.exceptions import DownloaderError
from .dialogs.add_task_dialog import AddTaskDialog

# 创建日志记录器
logger = get_logger("gui")

class LogHandler(QTextEdit):
    """日志处理器，将日志输出到QTextEdit。"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        """初始化日志处理器。"""
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        
    def append_log(self, text: str) -> None:
        """添加日志文本。
        
        Args:
            text: 日志文本
        """
        self.append(text)
        # 滚动到底部
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()
        )

class AsyncDownloader(QThread):
    """异步下载线程。"""
    
    finished = Signal(dict)  # 下载完成信号
    error = Signal(str)  # 错误信号
    
    def __init__(self, coro, parent=None):
        """初始化异步下载线程。
        
        Args:
            coro: 异步协程
            parent: 父对象
        """
        super().__init__(parent)
        self.coro = coro
        self.loop = None
        
    def run(self):
        """运行下载线程。"""
        try:
            # 创建事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # 运行协程
            result = self.loop.run_until_complete(self.coro)
            self.finished.emit(result)
            
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            self.error.emit(str(e))
            
        finally:
            # 清理事件循环
            if self.loop:
                self.loop.close()

class DownloadThread(QThread):
    """下载线程。
    
    处理单个下载任务的执行。
    支持进度更新和状态回调。
    
    Signals:
        progress_updated: 进度更新信号
        status_updated: 状态更新信号
        download_finished: 下载完成信号
        download_error: 下载错误信号
    """
    
    progress_updated = Signal(float, str)  # 进度值, 状态消息
    status_updated = Signal(str)  # 状态消息
    download_finished = Signal(dict)  # 下载结果
    download_error = Signal(str)  # 错误消息
    
    def __init__(
        self,
        downloader: BaseDownloader,
        url: str,
        save_dir: str,
        progress_bar: Optional[QProgressBar] = None,
        parent: Optional[QWidget] = None
    ):
        """初始化下载线程。
        
        Args:
            downloader: 下载器实例
            url: 下载URL
            save_dir: 保存目录
            progress_bar: 进度条控件
            parent: 父控件
        """
        super().__init__(parent)
        self.downloader = downloader
        self.url = url
        self.save_dir = save_dir
        self.progress_bar = progress_bar
        
        # 暂停和取消标志
        self._paused = False
        self._canceled = False
        
        # 下载状态
        self.current_file = ""
        self.download_speed = 0
        self.eta = 0
        self.total_size = 0
        self.downloaded_size = 0
        
        # 创建计时器用于更新UI
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_ui)
        self._update_timer.start(100)  # 100ms更新一次
        
    def run(self):
        """执行下载任务。"""
        try:
            # 设置进度回调
            self.downloader.progress_callback = self._progress_callback
            
            # 开始下载
            self.status_updated.emit("正在准备下载...")
            result = self.downloader.download(self.url)
            
            if self._canceled:
                self.status_updated.emit("下载已取消")
                return
                
            self.download_finished.emit(result)
            self.status_updated.emit("下载完成")
            
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            self.download_error.emit(str(e))
            self.status_updated.emit("下载失败")
            
        finally:
            self._update_timer.stop()
            
    def pause(self):
        """暂停下载。"""
        if not self._paused:
            self._paused = True
            if self.progress_bar:
                self.progress_bar.setEnabled(False)  # 冻结进度条
            self.status_updated.emit("下载已暂停")
            logger.info("下载已暂停")
            
    def resume(self):
        """恢复下载。"""
        if self._paused:
            self._paused = False
            if self.progress_bar:
                self.progress_bar.setEnabled(True)  # 恢复进度条
            self.status_updated.emit("正在下载...")
            logger.info("下载已恢复")
            
    def cancel(self):
        """取消下载。"""
        self._canceled = True
        self.downloader.cancel()
        self.status_updated.emit("正在取消...")
        logger.info("下载已取消")
        
    def _progress_callback(self, progress: float, status: str):
        """进度回调函数。
        
        Args:
            progress: 进度值(0-1)
            status: 状态消息
        """
        if self._paused:
            return
            
        self.progress_updated.emit(progress, status)
        
        # 解析状态消息
        try:
            if "下载中" in status:
                parts = status.split(" - ")
                self.current_file = parts[0].replace("下载中: ", "")
                if len(parts) > 1:
                    speed_part = parts[1]
                    if "MB/s" in speed_part:
                        self.download_speed = float(speed_part.replace("MB/s", ""))
                if len(parts) > 2:
                    eta_part = parts[2]
                    if "剩余" in eta_part and "秒" in eta_part:
                        self.eta = int(eta_part.replace("剩余", "").replace("秒", ""))
        except Exception:
            pass
            
    def _update_ui(self):
        """更新UI显示。"""
        if not self._paused and self.progress_bar:
            # 更新进度条文本
            text_parts = []
            if self.current_file:
                text_parts.append(os.path.basename(self.current_file))
            if self.download_speed > 0:
                text_parts.append(f"{self.download_speed:.1f}MB/s")
            if self.eta > 0:
                text_parts.append(f"剩余{self.eta}秒")
                
            if text_parts:
                self.progress_bar.setFormat("%p% - " + " - ".join(text_parts))

class ThemeManager:
    """主题管理器。
    
    管理应用程序的主题设置。
    支持明暗主题切换。
    
    Attributes:
        settings: QSettings, 应用程序设置
        dark_mode: bool, 是否为暗色主题
    """
    
    def __init__(self):
        """初始化主题管理器。"""
        self.settings = QSettings()
        self.dark_mode = self.settings.value("theme/dark_mode", False, type=bool)
        
    def switch_dark_mode(self, enable: bool):
        """切换暗色主题。
        
        Args:
            enable: 是否启用暗色主题
        """
        try:
            # 保存设置
            self.dark_mode = enable
            self.settings.setValue("theme/dark_mode", enable)
            
            # 获取应用程序实例
            app = QApplication.instance()
            if not app:
                return
                
            # 加载并应用样式表
            style = load_style(enable)
            app.setStyleSheet(style)
            
            # 更新调色板
            palette = QPalette()
            if enable:
                # 暗色主题颜色
                palette.setColor(QPalette.Window, QColor(53, 53, 53))
                palette.setColor(QPalette.WindowText, Qt.white)
                palette.setColor(QPalette.Base, QColor(25, 25, 25))
                palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
                palette.setColor(QPalette.ToolTipBase, Qt.white)
                palette.setColor(QPalette.ToolTipText, Qt.white)
                palette.setColor(QPalette.Text, Qt.white)
                palette.setColor(QPalette.Button, QColor(53, 53, 53))
                palette.setColor(QPalette.ButtonText, Qt.white)
                palette.setColor(QPalette.BrightText, Qt.red)
                palette.setColor(QPalette.Link, QColor(42, 130, 218))
                palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
                palette.setColor(QPalette.HighlightedText, Qt.black)
            else:
                # 亮色主题颜色
                palette = app.style().standardPalette()
                
            # 应用调色板
            app.setPalette(palette)
            
            # 强制刷新所有控件
            for widget in app.allWidgets():
                # 更新调色板
                widget.setPalette(palette)
                # 更新样式表
                widget.setStyleSheet(widget.styleSheet())
                # 强制重绘
                widget.update()
                
            logger.info(f"主题切换{'成功' if enable else '关闭'}")
            
        except Exception as e:
            logger.error(f"切换主题失败: {str(e)}")
            
    def apply_theme(self):
        """应用当前主题设置。"""
        self.switch_dark_mode(self.dark_mode)

class MainWindow(QMainWindow):
    """主窗口。
    
    提供以下功能：
    1. 任务列表
    2. 添加任务
    3. 管理任务
    4. 设置
    5. 帮助
    6. 系统托盘
    
    Attributes:
        scheduler: 下载调度器
        settings: 配置信息
    """
    
    def __init__(
        self,
        scheduler: DownloadScheduler,
        settings: Dict[str, Any]
    ):
        """初始化主窗口。
        
        Args:
            scheduler: 下载调度器
            settings: 配置信息
        """
        super().__init__()
        
        self.scheduler = scheduler
        self.settings = settings
        
        # 设置窗口
        self.setWindowTitle("视频下载器")
        self.setMinimumSize(800, 600)
        
        # 创建界面
        self._create_ui()
        
        # 创建托盘图标
        self._create_tray_icon()
        
        # 创建定时器
        self._create_timer()
        
    def _create_ui(self):
        """创建界面。"""
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # 创建工具栏
        toolbar = QHBoxLayout()
        
        # 添加按钮
        add_button = QPushButton("添加")
        add_button.clicked.connect(self._add_task)
        toolbar.addWidget(add_button)
        
        # 暂停/继续按钮
        self.pause_button = QPushButton("暂停全部")
        self.pause_button.clicked.connect(self._toggle_all)
        toolbar.addWidget(self.pause_button)
        
        # 清除按钮
        clear_button = QPushButton("清除已完成")
        clear_button.clicked.connect(self._clear_completed)
        toolbar.addWidget(clear_button)
        
        # 设置按钮
        settings_button = QPushButton("设置")
        settings_button.clicked.connect(self._show_settings)
        toolbar.addWidget(settings_button)
        
        # 帮助按钮
        help_button = QPushButton("帮助")
        help_button.clicked.connect(self._show_help)
        toolbar.addWidget(help_button)
        
        toolbar.addStretch()
        
        # 状态标签
        self.status_label = QLabel()
        toolbar.addWidget(self.status_label)
        
        layout.addLayout(toolbar)
        
        # 创建任务表格
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(7)
        self.task_table.setHorizontalHeaderLabels([
            "ID",
            "URL",
            "状态",
            "大小",
            "进度",
            "速度",
            "剩余时间"
        ])
        
        # 设置列宽
        header = self.task_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
        # 设置右键菜单
        self.task_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_table.customContextMenuRequested.connect(
            self._show_context_menu
        )
        
        layout.addWidget(self.task_table)
        
        # 创建状态栏
        self.statusBar().showMessage("就绪")
        
    def _create_tray_icon(self):
        """创建托盘图标。"""
        # 创建托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(
            self.style().standardIcon(QStyle.SP_ComputerIcon)
        )
        
        # 创建托盘菜单
        tray_menu = QMenu()
        
        # 显示/隐藏
        show_action = QAction("显示", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        # 退出
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
    def _create_timer(self):
        """创建定时器。"""
        # 创建更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_tasks)
        self.update_timer.start(1000)  # 每秒更新一次
        
    def _add_task(self):
        """添加下载任务。"""
        dialog = AddTaskDialog(self.settings, self)
        dialog.task_added.connect(self._on_task_added)
        dialog.exec()
        
    def _on_task_added(self, task_params: Dict[str, Any]):
        """处理任务添加。
        
        Args:
            task_params: 任务参数
        """
        try:
            # 添加任务
            task_id = self.scheduler.add_task(
                task_params['url'],
                task_params['save_dir'],
                priority=task_params['priority'],
                speed_limit=task_params['speed_limit']
            )
            
            # 更新界面
            self._update_tasks()
            
            # 显示提示
            self.statusBar().showMessage(f"任务添加成功: {task_id}")
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "错误",
                f"添加任务失败: {str(e)}"
            )
            
    def _toggle_all(self):
        """暂停/继续所有任务。"""
        if self.scheduler._paused:
            self.scheduler.resume_all()
            self.pause_button.setText("暂停全部")
        else:
            self.scheduler.pause_all()
            self.pause_button.setText("继续全部")
            
    def _clear_completed(self):
        """清除已完成任务。"""
        # 确认清除
        reply = QMessageBox.question(
            self,
            "确认清除",
            "是否清除所有已完成的任务？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        try:
            # 获取已完成任务
            completed_tasks = list(self.scheduler._completed_tasks.values())
            
            # 清除任务
            for task in completed_tasks:
                self.scheduler._completed_tasks.pop(task.id)
                
            # 更新界面
            self._update_tasks()
            
            # 显示提示
            self.statusBar().showMessage(
                f"已清除 {len(completed_tasks)} 个已完成任务"
            )
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "错误",
                f"清除任务失败: {str(e)}"
            )
        
    def _show_settings(self):
        """显示设置对话框。"""
        dialog = SettingsDialog(self.settings, self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()
        
    def _show_help(self):
        """显示帮助对话框。"""
        dialog = HelpDialog(self)
        dialog.exec()
        
    def _show_context_menu(self, pos):
        """显示右键菜单。
        
        Args:
            pos: 菜单位置
        """
        # 获取选中的任务
        row = self.task_table.rowAt(pos.y())
        if row < 0:
            return
            
        # 创建菜单
        menu = QMenu()
        
        # 打开文件
        open_action = QAction("打开文件", self)
        open_action.triggered.connect(
            lambda: self._open_file(row)
        )
        menu.addAction(open_action)
        
        # 打开目录
        open_dir_action = QAction("打开目录", self)
        open_dir_action.triggered.connect(
            lambda: self._open_directory(row)
        )
        menu.addAction(open_dir_action)
        
        menu.addSeparator()
        
        # 暂停/继续
        task_id = self.task_table.item(row, 0).text()
        task = self.scheduler.get_task(task_id)
        if task and task.status == "downloading":
            pause_action = QAction("暂停", self)
            pause_action.triggered.connect(
                lambda: self._pause_task(row)
            )
            menu.addAction(pause_action)
        elif task and task.status == "paused":
            resume_action = QAction("继续", self)
            resume_action.triggered.connect(
                lambda: self._resume_task(row)
            )
            menu.addAction(resume_action)
            
        # 重试
        if task and task.status == "failed":
            retry_action = QAction("重试", self)
            retry_action.triggered.connect(
                lambda: self._retry_task(row)
            )
            menu.addAction(retry_action)
            
        menu.addSeparator()
        
        # 删除
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(
            lambda: self._delete_task(row)
        )
        menu.addAction(delete_action)
        
        # 显示菜单
        menu.exec(self.task_table.viewport().mapToGlobal(pos))
        
    def _update_tasks(self):
        """更新任务列表。"""
        # 获取所有任务
        tasks = (
            list(self.scheduler._active_tasks.values()) +
            list(self.scheduler._completed_tasks.values()) +
            list(self.scheduler._failed_tasks.values())
        )
        
        # 更新表格
        self.task_table.setRowCount(len(tasks))
        for i, task in enumerate(tasks):
            # ID
            id_item = QTableWidgetItem(task.id)
            self.task_table.setItem(i, 0, id_item)
            
            # URL
            url_item = QTableWidgetItem(task.url)
            self.task_table.setItem(i, 1, url_item)
            
            # 状态
            status_item = QTableWidgetItem(task.status)
            self.task_table.setItem(i, 2, status_item)
            
            # 大小
            size_item = QTableWidgetItem(
                self._format_size(task.total_size)
            )
            self.task_table.setItem(i, 3, size_item)
            
            # 进度
            progress = (
                task.downloaded_size / task.total_size * 100
                if task.total_size > 0 else 0
            )
            progress_item = QTableWidgetItem(f"{progress:.1f}%")
            self.task_table.setItem(i, 4, progress_item)
            
            # 速度
            speed_item = QTableWidgetItem(
                self._format_speed(task.current_speed)
            )
            self.task_table.setItem(i, 5, speed_item)
            
            # 剩余时间
            time_item = QTableWidgetItem(
                str(task.remaining_time)
                if task.remaining_time else "-"
            )
            self.task_table.setItem(i, 6, time_item)
            
        # 更新状态栏
        stats = self.scheduler.get_stats()
        self.status_label.setText(
            f"任务: {stats['total_tasks']} "
            f"活动: {stats['active_tasks']} "
            f"完成: {stats['completed_tasks']} "
            f"失败: {stats['failed_tasks']} "
            f"速度: {self._format_speed(stats['current_speed'])}"
        )
        
    def _format_size(self, size: int) -> str:
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
            
    def _format_speed(self, speed: int) -> str:
        """格式化下载速度。
        
        Args:
            speed: 下载速度(bytes/s)
            
        Returns:
            str: 格式化后的速度
        """
        if speed < 1024:
            return f"{speed} B/s"
        elif speed < 1024 * 1024:
            return f"{speed/1024:.1f} KB/s"
        elif speed < 1024 * 1024 * 1024:
            return f"{speed/1024/1024:.1f} MB/s"
        else:
            return f"{speed/1024/1024/1024:.1f} GB/s"
            
    def _open_file(self, row: int):
        """打开文件。
        
        Args:
            row: 行号
        """
        task_id = self.task_table.item(row, 0).text()
        task = self.scheduler.get_task(task_id)
        if task and task.save_path.exists():
            os.startfile(task.save_path)
            
    def _open_directory(self, row: int):
        """打开目录。
        
        Args:
            row: 行号
        """
        task_id = self.task_table.item(row, 0).text()
        task = self.scheduler.get_task(task_id)
        if task and task.save_path.parent.exists():
            os.startfile(task.save_path.parent)
            
    def _pause_task(self, row: int):
        """暂停任务。
        
        Args:
            row: 行号
        """
        task_id = self.task_table.item(row, 0).text()
        self.scheduler.pause_task(task_id)
        
    def _resume_task(self, row: int):
        """继续任务。
        
        Args:
            row: 行号
        """
        task_id = self.task_table.item(row, 0).text()
        self.scheduler.resume_task(task_id)
        
    def _retry_task(self, row: int):
        """重试任务。
        
        Args:
            row: 行号
        """
        task_id = self.task_table.item(row, 0).text()
        task = self.scheduler.get_task(task_id)
        if task:
            self.scheduler.add_task(
                task.url,
                task.save_path,
                priority=task.priority,
                speed_limit=task.speed_limit,
                chunk_size=task.chunk_size,
                buffer_size=task.buffer_size,
                retries=task.retries,
                timeout=task.timeout,
                headers=task.headers,
                cookies=task.cookies
            )
            
    def _delete_task(self, row: int):
        """删除任务。
        
        Args:
            row: 行号
        """
        task_id = self.task_table.item(row, 0).text()
        task = self.scheduler.get_task(task_id)
        
        if task:
            # 确认删除
            reply = QMessageBox.question(
                self,
                "确认删除",
                "是否同时删除已下载的文件？",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Cancel:
                return
                
            try:
                # 取消任务
                self.scheduler.cancel_task(task_id)
                
                # 删除文件
                if reply == QMessageBox.Yes and task.save_path.exists():
                    task.save_path.unlink()
                    
                # 从列表中移除
                self.task_table.removeRow(row)
                
                # 显示提示
                self.statusBar().showMessage(f"任务已删除: {task_id}")
                
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "错误",
                    f"删除任务失败: {str(e)}"
                )
                
    def _on_settings_changed(self, settings: Dict[str, Any]):
        """处理设置变更。
        
        Args:
            settings: 新的设置
        """
        self.settings = settings
        
        # 更新调度器配置
        self.scheduler.max_concurrent = settings['max_concurrent']
        self.scheduler.max_retries = settings['max_retries']
        self.scheduler.default_timeout = settings['default_timeout']
        
        # 保存设置
        settings_file = Path("config/settings.json")
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
            
    def closeEvent(self, event):
        """处理关闭事件。
        
        Args:
            event: 关闭事件
        """
        if self.tray_icon.isVisible():
            QMessageBox.information(
                self,
                "提示",
                '程序将继续在后台运行。要退出程序，请右键点击托盘图标并选择"退出"。'
            )
            self.hide()
            event.ignore()
        else:
            # 停止调度器
            self.scheduler.stop()
            event.accept()

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 