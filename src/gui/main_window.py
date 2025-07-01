#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频下载器主窗口模块。

实现主要的GUI界面和交互逻辑。
使用迅雷12风格的现代界面设计。
"""

import sys
import os
import asyncio
from asyncio import AbstractEventLoop
from concurrent.futures import ThreadPoolExecutor
from enum import Enum, auto

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
    QHeaderView,
    QFrame,
    QStackedWidget,
    QToolButton,
    QSpinBox,
    QCheckBox,
    QButtonGroup,
    QScrollArea,
    QGridLayout,
    QTabWidget,
    QListWidget,
    QListWidgetItem
)
from PySide6.QtCore import Qt, Slot, Signal, QTimer, QThread, QSettings, QSize, QPoint, QEvent, QObject
from PySide6.QtGui import (
    QIcon, 
    QPalette, 
    QColor, 
    QAction,
    QFont,
    QPainter,
    QPen,
    QBrush,
    QLinearGradient
)

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
from src.core.settings import Settings
from .widgets.download_list import DownloadList
from .widgets.task_card import TaskCard
from ..core.download_task import DownloadTask, TaskStatus
from .creator_monitor import CreatorMonitorDialog
from .settings_page import SettingsPage
from .pages.downloading_page import DownloadingPage
from .pages.completed_page import CompletedPage
from .pages.recycle_page import RecyclePage

# 创建日志记录器
logger = get_logger("gui")

class LogHandler(QTextEdit):
    """日志处理器，将日志输出到QTextEdit。
    
    支持不同级别日志的彩色显示：
    - DEBUG: 灰色
    - INFO: 黑色
    - WARNING: 橙色
    - ERROR: 红色
    - CRITICAL: 深红色
    """
    
    # 日志级别对应的颜色
    COLORS = {
        'DEBUG': '#808080',      # 灰色
        'INFO': '#000000',       # 黑色
        'WARNING': '#FFA500',    # 橙色
        'ERROR': '#FF0000',      # 红色
        'CRITICAL': '#8B0000'    # 深红色
    }
    
    def __init__(self, parent: Optional[QWidget] = None):
        """初始化日志处理器。"""
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        
        # 设置字体
        font = self.font()
        font.setFamily("Consolas")  # 使用等宽字体
        self.setFont(font)
        
    def append_log(self, text: str) -> None:
        """添加日志文本。
        
        支持解析日志级别并使用对应的颜色显示。
        
        Args:
            text: 日志文本
        """
        try:
            # 解析日志级别
            level = 'INFO'  # 默认级别
            for level_name in self.COLORS.keys():
                if f'[{level_name}]' in text:
                    level = level_name
                    break
            
            # 设置颜色
            color = self.COLORS.get(level, self.COLORS['INFO'])
            formatted_text = f'<span style="color: {color};">{text}</span>'
            
            # 添加日志
            self.append(formatted_text)
            
            # 滚动到底部
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().maximum()
            )
            
        except Exception as e:
            # 如果解析失败，使用默认格式添加
            super().append(text)
            logger.error(f"格式化日志失败: {str(e)}")
            
    def clear_logs(self):
        """清空日志。"""
        self.clear()

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
    支持异步下载。
    
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
        self.loop = None
        
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
        """运行下载线程。"""
        try:
            # 创建事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # 设置进度回调
            self.downloader.progress_callback = self._progress_callback
            
            # 运行下载任务
            result = self.loop.run_until_complete(
                self.downloader.download(self.url)
            )
            
            # 发送完成信号
            self.download_finished.emit(result)
            
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            self.download_error.emit(str(e))
            
        finally:
            # 清理事件循环
            if self.loop:
                self.loop.close()
                self.loop = None
                
    def pause(self):
        """暂停下载。"""
        self._paused = True
        self.status_updated.emit("已暂停")
        
    def resume(self):
        """恢复下载。"""
        self._paused = False
        self.status_updated.emit("正在下载")
        
    def cancel(self):
        """取消下载。"""
        self._canceled = True
        if self.downloader:
            self.downloader.cancel()
        self.status_updated.emit("已取消")
        
    def _progress_callback(self, progress: float, status: str):
        """进度回调函数。
        
        Args:
            progress: 进度值（0-1）
            status: 状态消息
        """
        if self._canceled:
            return
            
        if self._paused:
            return
            
        # 更新进度
        self.progress_updated.emit(progress, status)
        
        # 解析状态消息中的下载信息
        try:
            if "speed" in status:
                speed_str = status.split("speed: ")[1].split("/s")[0]
                self.download_speed = self._parse_speed(speed_str)
                
            if "ETA" in status:
                eta_str = status.split("ETA: ")[1].split()[0]
                self.eta = self._parse_time(eta_str)
                
        except Exception:
            pass
            
    def _parse_speed(self, speed_str: str) -> float:
        """解析速度字符串。
        
        Args:
            speed_str: 速度字符串（如 "1.2MB"）
            
        Returns:
            float: 速度值（字节/秒）
        """
        try:
            value = float(speed_str[:-2])
            unit = speed_str[-2:]
            multiplier = {
                'B': 1,
                'KB': 1024,
                'MB': 1024 * 1024,
                'GB': 1024 * 1024 * 1024
            }.get(unit, 1)
            return value * multiplier
        except:
            return 0
            
    def _parse_time(self, time_str: str) -> int:
        """解析时间字符串。
        
        Args:
            time_str: 时间字符串（如 "01:23"）
            
        Returns:
            int: 秒数
        """
        try:
            parts = time_str.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            return 0
        except:
            return 0
            
    def _update_ui(self):
        """更新UI显示。"""
        if self.progress_bar and not self._canceled:
            # 更新进度条提示
            if self.download_speed > 0:
                speed_str = self._format_speed(self.download_speed)
                if self.eta > 0:
                    self.progress_bar.setToolTip(
                        f"下载速度: {speed_str}/s\n"
                        f"剩余时间: {self._format_time(self.eta)}"
                    )
                else:
                    self.progress_bar.setToolTip(f"下载速度: {speed_str}/s")
                    
    def _format_speed(self, speed: float) -> str:
        """格式化速度值。
        
        Args:
            speed: 速度值（字节/秒）
            
        Returns:
            str: 格式化后的速度字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if speed < 1024:
                return f"{speed:.1f}{unit}"
            speed /= 1024
        return f"{speed:.1f}TB"
        
    def _format_time(self, seconds: int) -> str:
        """格式化时间。
        
        Args:
            seconds: 秒数
            
        Returns:
            str: 格式化后的时间字符串
        """
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

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

class NavButton(QToolButton):
    """自定义导航按钮。"""
    
    def __init__(self, text: str, icon_name: str = None, parent=None):
        """初始化导航按钮。
        
        Args:
            text: 按钮文本
            icon_name: 图标名称
            parent: 父窗口
        """
        super().__init__(parent)
        self.setText(text)
        if icon_name:
            self.setIcon(QIcon(f":/icons/{icon_name}"))
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setAutoRaise(True)
        self.setCheckable(True)
        self.setMinimumHeight(40)
        self.setIconSize(QSize(20, 20))
        
        # 设置样式
        self.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 5px 10px;
                text-align: left;
                font-size: 14px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QToolButton:checked {
                background-color: rgba(255, 255, 255, 0.2);
                color: #1890ff;
            }
        """)

class NavigationBar(QWidget):
    """左侧导航栏。"""
    
    page_changed = Signal(int)
    
    def __init__(self, parent=None):
        """初始化导航栏。"""
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setStyleSheet("""
            NavigationBar {
                background-color: white;
                border-right: 1px solid #f0f0f0;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Logo区域
        logo_widget = QWidget()
        logo_widget.setFixedHeight(60)
        logo_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border-bottom: 1px solid #f0f0f0;
            }
        """)
        
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(20, 0, 20, 0)
        
        logo = QLabel("视频下载器")
        logo.setStyleSheet("""
            QLabel {
                color: #1f2329;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        logo_layout.addWidget(logo)
        logo_widget.setLayout(logo_layout)
        layout.addWidget(logo_widget)
        
        # 导航按钮
        nav_widget = QWidget()
        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(8, 16, 8, 16)
        nav_layout.setSpacing(4)
        
        self.downloading_btn = self._create_nav_button("下载中", "downloading", True)
        self.completed_btn = self._create_nav_button("已完成", "completed")
        self.recycled_btn = self._create_nav_button("回收站", "recycled")
        
        nav_layout.addWidget(self.downloading_btn)
        nav_layout.addWidget(self.completed_btn)
        nav_layout.addWidget(self.recycled_btn)
        nav_layout.addStretch()
        
        # 设置按钮
        self.settings_btn = self._create_nav_button("设置", "settings")
        nav_layout.addWidget(self.settings_btn)
        
        nav_widget.setLayout(nav_layout)
        layout.addWidget(nav_widget)
        
        self.setLayout(layout)
        
        # 连接信号
        self.downloading_btn.clicked.connect(lambda: self._switch_page(0))
        self.completed_btn.clicked.connect(lambda: self._switch_page(1))
        self.recycled_btn.clicked.connect(lambda: self._switch_page(2))
        self.settings_btn.clicked.connect(lambda: self._switch_page(3))
        
    def _create_nav_button(self, text: str, icon_name: str, checked: bool = False) -> QPushButton:
        """创建导航按钮。
        
        Args:
            text: 按钮文本
            icon_name: 图标名称
            checked: 是否选中
            
        Returns:
            QPushButton: 导航按钮
        """
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedHeight(40)
        
        # 设置图标
        icon = QIcon(f"resources/icons/{icon_name}.svg")
        btn.setIcon(icon)
        btn.setIconSize(QSize(18, 18))
        
        # 设置样式
        btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                text-align: left;
                font-size: 14px;
                color: #4e5969;
                background-color: transparent;
            }
            QPushButton:checked {
                background-color: #e8f3ff;
                color: #1890ff;
                font-weight: 500;
            }
            QPushButton:hover:!checked {
                background-color: #f2f3f5;
                color: #1f2329;
            }
        """)
        
        return btn
        
    def _switch_page(self, index: int):
        """切换页面。
        
        Args:
            index: 页面索引
        """
        buttons = [
            self.downloading_btn,
            self.completed_btn,
            self.recycled_btn,
            self.settings_btn
        ]
        
        for i, btn in enumerate(buttons):
            btn.setChecked(i == index)
            
        self.page_changed.emit(index)

class WindowButton(QPushButton):
    """窗口控制按钮。"""
    
    def __init__(self, button_type: str, parent=None):
        """初始化窗口按钮。
        
        Args:
            button_type: 按钮类型(min/max/close)
            parent: 父窗口
        """
        super().__init__(parent)
        self.button_type = button_type
        self.setFixedSize(46, 40)
        self.setStyleSheet(self._get_style())
        
    def _get_style(self) -> str:
        """获取按钮样式。"""
        if self.button_type == "close":
            return """
                QPushButton {
                    border: none;
                    background-color: transparent;
                }
                QPushButton:hover {
                    background-color: #ff4d4f;
                }
            """
        else:
            return """
                QPushButton {
                    border: none;
                    background-color: transparent;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 0.1);
                }
            """
            
    def paintEvent(self, event):
        """绘制按钮图标。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 设置画笔
        pen = QPen(Qt.white if self.button_type == "close" and self.underMouse() else Qt.black)
        pen.setWidth(1)
        painter.setPen(pen)
        
        # 绘制图标
        if self.button_type == "min":
            painter.drawLine(18, 20, 28, 20)
        elif self.button_type == "max":
            painter.drawRect(18, 15, 10, 10)
        elif self.button_type == "close":
            painter.drawLine(18, 15, 28, 25)
            painter.drawLine(28, 15, 18, 25)

class TitleBar(QWidget):
    """自定义标题栏。"""
    
    def __init__(self, parent=None):
        """初始化标题栏。"""
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setStyleSheet("""
            TitleBar {
                background-color: white;
                border-bottom: 1px solid #f0f0f0;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(20, 0, 10, 0)
        layout.setSpacing(10)
        
        # 标题
        title = QLabel("视频下载器")
        title.setStyleSheet("""
            QLabel {
                color: #1f2329;
                font-size: 16px;
                font-weight: 500;
            }
        """)
        layout.addWidget(title)
        layout.addStretch()
        
        # 窗口控制按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(0)
        
        # 最小化按钮
        min_btn = self._create_window_button("minimize")
        min_btn.clicked.connect(self.window().showMinimized)
        
        # 最大化按钮
        self.max_btn = self._create_window_button("maximize")
        self.max_btn.clicked.connect(self._toggle_maximize)
        
        # 关闭按钮
        close_btn = self._create_window_button("close")
        close_btn.clicked.connect(self.window().close)
        
        btn_layout.addWidget(min_btn)
        btn_layout.addWidget(self.max_btn)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
    def _create_window_button(self, button_type: str) -> QPushButton:
        """创建窗口控制按钮。
        
        Args:
            button_type: 按钮类型(minimize/maximize/close)
            
        Returns:
            QPushButton: 窗口控制按钮
        """
        btn = QPushButton()
        btn.setFixedSize(46, 50)
        
        # 设置图标
        icon = QIcon(f"resources/icons/{button_type}.svg")
        btn.setIcon(icon)
        btn.setIconSize(QSize(16, 16))
        
        # 设置样式
        if button_type == "close":
            btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background-color: transparent;
                }
                QPushButton:hover {
                    background-color: #ff4d4f;
                }
                QPushButton:hover QIcon {
                    fill: white;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background-color: transparent;
                }
                QPushButton:hover {
                    background-color: #f5f6f7;
                }
            """)
            
        return btn
        
    def _toggle_maximize(self):
        """切换最大化状态。"""
        window = self.window()
        if window.isMaximized():
            window.showNormal()
            self.max_btn.setIcon(QIcon("resources/icons/maximize.svg"))
        else:
            window.showMaximized()
            self.max_btn.setIcon(QIcon("resources/icons/restore.svg"))
            
    def mousePressEvent(self, event):
        """鼠标按下事件。"""
        if event.button() == Qt.LeftButton:
            self.window().drag_pos = event.globalPos() - self.window().pos()
            event.accept()
            
    def mouseMoveEvent(self, event):
        """鼠标移动事件。"""
        if event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPos() - self.window().drag_pos)
            event.accept()

class MainWindow(QMainWindow):
    """主窗口类
    
    采用现代化三栏布局:
    - 左侧导航栏(220px): 显示主要功能入口
    - 中间内容区: 显示下载任务列表
    - 右侧信息栏(300px): 显示任务详情和设置
    
    设计特点:
    - Material Design风格
    - 自适应布局
    - 完善的暗色主题支持
    - 统一的视觉风格
    """
    
    # Material Design 配色方案
    COLORS = {
        'primary': '#1976D2',      # 主色调
        'primary_dark': '#1565C0', # 主色调暗色
        'primary_light': '#42A5F5',# 主色调亮色
        'accent': '#FF4081',       # 强调色
        'warn': '#F44336',         # 警告色
        'background': '#FAFAFA',   # 背景色
        'surface': '#FFFFFF',      # 表面色
        'on_primary': '#FFFFFF',   # 主色调上的文字
        'on_surface': '#000000',   # 表面上的文字
        'divider': '#E0E0E0',      # 分隔线
        
        # 暗色主题
        'dark': {
            'background': '#121212',
            'surface': '#1E1E1E',
            'primary': '#90CAF9',
            'on_surface': '#FFFFFF',
            'divider': '#2D2D2D'
        }
    }
    
    def __init__(self, scheduler=None, settings=None):
        super().__init__()
        self.settings = settings or Settings()
        self.scheduler = scheduler or DownloadScheduler(self.settings)
        
        # 初始化界面
        self._setup_ui()
        self._setup_styles()
        self._connect_signals()
        
        # 创建定时器更新速度显示
        self._setup_speed_timer()
        
        # 恢复窗口状态
        self._restore_window_state()
        
    def _setup_ui(self):
        """创建界面布局"""
        # 设置窗口基本属性
        self.setWindowTitle("视频下载器")
        self.setMinimumSize(1200, 800)
        
        # 创建主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局(水平布局,包含三栏)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 左侧导航栏
        self.nav_bar = self._create_nav_bar()
        main_layout.addWidget(self.nav_bar)
        
        # 中间内容区
        self.content_area = self._create_content_area()
        main_layout.addWidget(self.content_area)
        
        # 右侧信息栏
        self.info_panel = self._create_info_panel()
        main_layout.addWidget(self.info_panel)
        
    def _create_nav_bar(self) -> QWidget:
        """创建左侧导航栏"""
        nav_bar = QWidget()
        nav_bar.setObjectName("navBar")
        nav_bar.setFixedWidth(220)
        
        layout = QVBoxLayout(nav_bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Logo区域
        logo = QLabel("视频下载器")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedHeight(60)
        layout.addWidget(logo)
        
        # 导航按钮
        nav_buttons = QWidget()
        nav_buttons.setObjectName("navButtons")
        buttons_layout = QVBoxLayout(nav_buttons)
        buttons_layout.setContentsMargins(8, 8, 8, 8)
        buttons_layout.setSpacing(4)
        
        # 添加导航按钮
        self.nav_group = QButtonGroup(self)
        for text, icon in [
            ("下载中", "downloading"),
            ("已完成", "completed"),
            ("回收站", "recycled"),
            ("创作者", "creators")
        ]:
            btn = self._create_nav_button(text, icon)
            buttons_layout.addWidget(btn)
            self.nav_group.addButton(btn)
            
        buttons_layout.addStretch()
        
        # 设置按钮
        settings_btn = self._create_nav_button("设置", "settings")
        buttons_layout.addWidget(settings_btn)
        
        layout.addWidget(nav_buttons)
        
        return nav_bar
        
    def _create_nav_button(self, text: str, icon: str) -> QPushButton:
        """创建导航按钮
        
        Args:
            text: 按钮文本
            icon: 图标名称
            
        Returns:
            QPushButton: 导航按钮
        """
        btn = QPushButton(text)
        btn.setObjectName("navButton")
        btn.setCheckable(True)
        btn.setFixedHeight(40)
        
        # 设置图标
        icon = QIcon(f":/icons/{icon}.svg")
        btn.setIcon(icon)
        btn.setIconSize(QSize(20, 20))
        
        return btn
        
    def _create_content_area(self) -> QWidget:
        """创建中间内容区"""
        content = QWidget()
        content.setObjectName("contentArea")
        
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 任务列表
        self.task_list = self._create_task_list()
        layout.addWidget(self.task_list)
        
        return content
        
    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        toolbar.setFixedHeight(60)
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(16, 0, 16, 0)
        
        # URL输入框
        self.url_input = QLineEdit()
        self.url_input.setObjectName("urlInput")
        self.url_input.setPlaceholderText("输入视频URL或粘贴多个链接(换行分隔)")
        layout.addWidget(self.url_input)
        
        # 添加按钮
        add_btn = QPushButton("添加任务")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._add_download_task)
        layout.addWidget(add_btn)
        
        return toolbar
        
    def _create_task_list(self) -> QListWidget:
        """创建任务列表"""
        task_list = QListWidget()
        task_list.setObjectName("taskList")
        task_list.setSpacing(1)
        task_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        
        return task_list
        
    def _create_info_panel(self) -> QWidget:
        """创建右侧信息面板"""
        panel = QWidget()
        panel.setObjectName("infoPanel")
        panel.setFixedWidth(300)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 全局状态
        status = self._create_status_widget()
        layout.addWidget(status)
        
        # 任务详情/设置页面
        self.detail_stack = QStackedWidget()
        self.detail_stack.setObjectName("detailStack")
        
        # 添加详情页
        self.task_detail = self._create_task_detail()
        self.settings_page = self._create_settings_page()
        
        self.detail_stack.addWidget(self.task_detail)
        self.detail_stack.addWidget(self.settings_page)
        
        layout.addWidget(self.detail_stack)
        
        return panel
        
    def _create_status_widget(self) -> QWidget:
        """创建状态显示组件"""
        status = QWidget()
        status.setObjectName("statusWidget")
        status.setFixedHeight(60)
        
        layout = QHBoxLayout(status)
        layout.setContentsMargins(16, 0, 16, 0)
        
        # 下载速度
        speed_layout = QVBoxLayout()
        speed_label = QLabel("下载速度")
        speed_label.setObjectName("statusLabel")
        self.speed_value = QLabel("0 KB/s")
        self.speed_value.setObjectName("statusValue")
        
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.speed_value)
        layout.addLayout(speed_layout)
        
        # 活动任务数
        task_layout = QVBoxLayout()
        task_label = QLabel("活动任务")
        task_label.setObjectName("statusLabel")
        self.task_count = QLabel("0")
        self.task_count.setObjectName("statusValue")
        
        task_layout.addWidget(task_label)
        task_layout.addWidget(self.task_count)
        layout.addLayout(task_layout)
        
        return status
        
    def _create_task_detail(self) -> QWidget:
        """创建任务详情页"""
        detail = QWidget()
        detail.setObjectName("taskDetail")
        
        layout = QVBoxLayout(detail)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # 标题
        title = QLabel("任务详情")
        title.setObjectName("detailTitle")
        layout.addWidget(title)
        
        # 详细信息
        info_widget = QWidget()
        info_widget.setObjectName("detailInfo")
        info_layout = QFormLayout(info_widget)
        info_layout.setContentsMargins(16, 16, 16, 16)
        info_layout.setSpacing(12)
        
        # 添加详情项
        self.detail_filename = QLabel()
        self.detail_size = QLabel()
        self.detail_progress = QLabel()
        self.detail_speed = QLabel()
        self.detail_eta = QLabel()
        
        info_layout.addRow("文件名:", self.detail_filename)
        info_layout.addRow("大小:", self.detail_size)
        info_layout.addRow("进度:", self.detail_progress)
        info_layout.addRow("速度:", self.detail_speed)
        info_layout.addRow("剩余时间:", self.detail_eta)
        
        layout.addWidget(info_widget)
        layout.addStretch()
        
        return detail
        
    def _setup_styles(self):
        """设置界面样式"""
        # 获取当前主题
        is_dark = self.settings.get('theme.dark_mode', False)
        colors = self.COLORS['dark'] if is_dark else self.COLORS
        
        # 主窗口样式
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {colors['background']};
            }}
            
            /* 导航栏 */
            #navBar {{
                background: {colors['surface']};
                border-right: 1px solid {colors['divider']};
            }}
            
            #logo {{
                color: {colors['primary']};
                font-size: 18px;
                font-weight: bold;
            }}
            
            #navButton {{
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                text-align: left;
                color: {colors['on_surface']};
                background: transparent;
            }}
            
            #navButton:hover {{
                background: {colors['primary']}20;
            }}
            
            #navButton:checked {{
                background: {colors['primary']}40;
                color: {colors['primary']};
            }}
            
            /* 内容区 */
            #contentArea {{
                background: {colors['background']};
            }}
            
            #toolbar {{
                background: {colors['surface']};
                border-bottom: 1px solid {colors['divider']};
            }}
            
            #urlInput {{
                border: 1px solid {colors['divider']};
                border-radius: 4px;
                padding: 8px 12px;
                background: {colors['background']};
                color: {colors['on_surface']};
                selection-background-color: {colors['primary']}40;
            }}
            
            #primaryButton {{
                background: {colors['primary']};
                color: {colors['on_primary']};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
            }}
            
            #primaryButton:hover {{
                background: {colors['primary_dark']};
            }}
            
            #taskList {{
                background: {colors['background']};
                border: none;
            }}
            
            /* 信息面板 */
            #infoPanel {{
                background: {colors['surface']};
                border-left: 1px solid {colors['divider']};
            }}
            
            #statusWidget {{
                border-bottom: 1px solid {colors['divider']};
            }}
            
            #statusLabel {{
                color: {colors['on_surface']}99;
                font-size: 12px;
            }}
            
            #statusValue {{
                color: {colors['on_surface']};
                font-size: 16px;
                font-weight: 500;
            }}
            
            #detailTitle {{
                color: {colors['on_surface']};
                font-size: 16px;
                font-weight: 500;
            }}
            
            #detailInfo {{
                background: {colors['background']};
                border-radius: 4px;
            }}
        """)
        
    def _setup_speed_timer(self):
        """设置速度更新定时器"""
        self.speed_timer = QTimer(self)
        self.speed_timer.timeout.connect(self._update_speed)
        self.speed_timer.start(1000)  # 每秒更新一次
        
    def _connect_signals(self):
        """连接信号槽"""
        pass
        
    def _add_download_task(self):
        """添加下载任务"""
        urls = self.url_input.text().split("\n")
        for url in urls:
            if url.strip():
                self._create_task_card(url.strip())
                
    def _create_task_card(self, url: str) -> QWidget:
        """创建任务卡片
        
        Args:
            url: 下载URL
            
        Returns:
            QWidget: 任务卡片组件
        """
        card = QWidget()
        card.setObjectName("taskCard")
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        
        # 缩略图
        thumbnail = QLabel()
        thumbnail.setObjectName("thumbnail")
        thumbnail.setFixedSize(160, 90)
        thumbnail.setStyleSheet(f"""
            background: {self.COLORS['surface']};
            border-radius: 4px;
        """)
        layout.addWidget(thumbnail)
        
        # 信息区域
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        
        # 标题和大小
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)
        
        title = QLabel(f"正在解析: {url}")
        title.setObjectName("taskTitle")
        title_layout.addWidget(title)
        
        size = QLabel("0 MB")
        size.setObjectName("taskSize")
        title_layout.addWidget(size)
        title_layout.addStretch()
        
        info_layout.addLayout(title_layout)
        
        # 进度条
        progress = QProgressBar()
        progress.setObjectName("taskProgress")
        progress.setValue(0)
        progress.setFixedHeight(4)
        info_layout.addWidget(progress)
        
        # 状态和控制
        status_layout = QHBoxLayout()
        status_layout.setSpacing(16)
        
        status = QLabel("等待中")
        status.setObjectName("taskStatus")
        status_layout.addWidget(status)
        
        speed = QLabel("0 KB/s")
        speed.setObjectName("taskSpeed")
        status_layout.addWidget(speed)
        status_layout.addStretch()
        
        # 控制按钮
        pause_btn = QPushButton("暂停")
        pause_btn.setObjectName("taskButton")
        status_layout.addWidget(pause_btn)
        
        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("taskButton")
        status_layout.addWidget(delete_btn)
        
        info_layout.addLayout(status_layout)
        layout.addLayout(info_layout)
        
        # 设置卡片样式
        card.setStyleSheet(f"""
            #taskCard {{
                background: {self.COLORS['surface']};
                border-radius: 4px;
            }}
            
            #taskTitle {{
                color: {self.COLORS['on_surface']};
                font-size: 14px;
                font-weight: 500;
            }}
            
            #taskSize {{
                color: {self.COLORS['on_surface']}99;
                font-size: 12px;
            }}
            
            #taskProgress {{
                background: {self.COLORS['divider']};
                border: none;
                border-radius: 2px;
            }}
            
            #taskProgress::chunk {{
                background: {self.COLORS['primary']};
                border-radius: 2px;
            }}
            
            #taskStatus, #taskSpeed {{
                color: {self.COLORS['on_surface']}99;
                font-size: 12px;
            }}
            
            #taskButton {{
                background: transparent;
                border: 1px solid {self.COLORS['divider']};
                border-radius: 4px;
                padding: 4px 12px;
                color: {self.COLORS['on_surface']};
                font-size: 12px;
            }}
            
            #taskButton:hover {{
                border-color: {self.COLORS['primary']};
                color: {self.COLORS['primary']};
            }}
        """)
        
        return card

    def _create_settings_page(self) -> QWidget:
        """创建设置页面"""
        from .settings_page import SettingsPage
        return SettingsPage(self.settings, self)
        
    def _load_settings(self):
        """加载设置"""
        try:
            # 下载设置
            self.path_input.setText(self.settings.get('download.save_dir', ''))
            self.threads_spin.setValue(self.settings.get('download.max_concurrent', 3))
            
            # 速度限制
            speed_limit = self.settings.get('download.speed_limit', 0)
            if speed_limit > 0:
                self.speed_limit_spin.setValue(speed_limit)
                speed_check = self.findChild(QCheckBox, "speedCheck")
                if speed_check:
                    speed_check.setChecked(True)
                    self.speed_limit_spin.setEnabled(True)
                
            # 代理设置
            self.proxy_check.setChecked(self.settings.get('proxy.enabled', False))
            self.proxy_type.setCurrentText(self.settings.get('proxy.type', 'HTTP'))
            self.proxy_input.setText(self.settings.get('proxy.host', ''))
            
            # 主题设置
            self.theme_combo.setCurrentText("暗色" if self.settings.get('theme.dark_mode', True) else "明亮")
            
        except Exception as e:
            logger.error(f"加载设置失败: {e}")
            QMessageBox.warning(self, "错误", f"加载设置失败: {e}")

    def _on_theme_changed(self, theme: str):
        """主题变更处理
        
        Args:
            theme: 主题名称
        """
        try:
            dark_mode = theme == "暗色"
            self.settings.set('theme.dark_mode', dark_mode)
            self.settings.save()
            
            # 更新主题
            if hasattr(self, 'theme_manager'):
                self.theme_manager.switch_dark_mode(dark_mode)
                
        except Exception as e:
            logger.error(f"切换主题失败: {e}")
            QMessageBox.warning(self, "错误", f"切换主题失败: {e}")

    def _setup_styles(self):
        """设置界面样式"""
        # 获取当前主题
        is_dark = self.settings.get('theme.dark_mode', False)
        colors = self.COLORS['dark'] if is_dark else self.COLORS
        
        # 主窗口样式
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {colors['background']};
            }}
            
            /* 导航栏 */
            #navBar {{
                background: {colors['surface']};
                border-right: 1px solid {colors['divider']};
            }}
            
            #logo {{
                color: {colors['primary']};
                font-size: 18px;
                font-weight: bold;
            }}
            
            #navButton {{
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                text-align: left;
                color: {colors['on_surface']};
                background: transparent;
            }}
            
            #navButton:hover {{
                background: {colors['primary']}20;
            }}
            
            #navButton:checked {{
                background: {colors['primary']}40;
                color: {colors['primary']};
            }}
            
            /* 内容区 */
            #contentArea {{
                background: {colors['background']};
            }}
            
            #toolbar {{
                background: {colors['surface']};
                border-bottom: 1px solid {colors['divider']};
            }}
            
            #urlInput {{
                border: 1px solid {colors['divider']};
                border-radius: 4px;
                padding: 8px 12px;
                background: {colors['background']};
                color: {colors['on_surface']};
                selection-background-color: {colors['primary']}40;
            }}
            
            #primaryButton {{
                background: {colors['primary']};
                color: {colors['on_primary']};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
            }}
            
            #primaryButton:hover {{
                background: {colors['primary_dark']};
            }}
            
            #taskList {{
                background: {colors['background']};
                border: none;
            }}
            
            /* 信息面板 */
            #infoPanel {{
                background: {colors['surface']};
                border-left: 1px solid {colors['divider']};
            }}
            
            #statusWidget {{
                border-bottom: 1px solid {colors['divider']};
            }}
            
            #statusLabel {{
                color: {colors['on_surface']}99;
                font-size: 12px;
            }}
            
            #statusValue {{
                color: {colors['on_surface']};
                font-size: 16px;
                font-weight: 500;
            }}
            
            #detailTitle {{
                color: {colors['on_surface']};
                font-size: 16px;
                font-weight: 500;
            }}
            
            #detailInfo {{
                background: {colors['background']};
                border-radius: 4px;
            }}
        """)
        
    def _setup_speed_timer(self):
        """设置速度更新定时器"""
        self.speed_timer = QTimer(self)
        self.speed_timer.timeout.connect(self._update_speed)
        self.speed_timer.start(1000)  # 每秒更新一次
        
    def _connect_signals(self):
        """连接信号槽"""
        pass
        
    def _update_speed(self):
        """更新速度显示"""
        # TODO: 从下载管理器获取实际速度
        import random
        download = random.randint(100, 2000)
        upload = random.randint(10, 500)
        
        self.speed_value.setText(f"{download} KB/s")
        self.task_count.setText(str(self.task_list.count()))
        
    def _restore_window_state(self):
        """恢复窗口状态"""
        settings = QSettings()
        geometry = settings.value("mainWindow/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            # 首次运行,居中显示
            screen = QApplication.primaryScreen().geometry()
            self.move(
                (screen.width() - self.width()) // 2,
                (screen.height() - self.height()) // 2
            )
            
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 保存窗口状态
        settings = QSettings()
        settings.setValue("mainWindow/geometry", self.saveGeometry())
        event.accept()

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 