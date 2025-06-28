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
    QStyleFactory
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
from .theme import ThemeManager, load_style
from .download_dialog import DownloadDialog
from .settings_dialog import SettingsDialog

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
    """下载器主窗口。"""
    
    # 自定义信号
    download_progress = Signal(float, str)  # 下载进度信号
    log_message = Signal(str)  # 日志消息信号
    
    def __init__(self):
        super().__init__()
        
        # 初始化主题管理器
        self.theme_manager = ThemeManager()
        
        # 初始化UI
        self._setup_ui()
        
        # 创建菜单栏
        self._create_menu_bar()
        
        # 设置日志处理
        self._setup_logging()
        
        # 初始化代理设置
        self.proxy = "http://127.0.0.1:7890"
        
        # 初始化cookie管理器
        self.cookie_manager = CookieManager()
        
        # 连接信号和槽
        self._connect_signals()
        
        # 初始化下载器
        self._init_downloader()
        
        # 保存活动的下载线程
        self.active_downloaders = []
        
        # 应用主题
        self.theme_manager.apply_theme()
        
    def _create_menu_bar(self) -> None:
        """创建菜单栏。"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        exit_action = file_menu.addAction("退出")
        exit_action.triggered.connect(self.close)
        
        # 账号菜单
        account_menu = menubar.addMenu("账号")
        
        # Twitter账号管理
        twitter_menu = account_menu.addMenu("Twitter")
        twitter_auth_action = twitter_menu.addAction("账号管理")
        twitter_auth_action.triggered.connect(
            lambda: self._show_cookie_dialog("twitter")
        )
        
        # YouTube账号管理
        youtube_menu = account_menu.addMenu("YouTube")
        youtube_auth_action = youtube_menu.addAction("账号管理")
        youtube_auth_action.triggered.connect(
            lambda: self._show_cookie_dialog("youtube")
        )
        
        # Pornhub账号管理
        pornhub_menu = account_menu.addMenu("Pornhub")
        pornhub_auth_action = pornhub_menu.addAction("账号管理")
        pornhub_auth_action.triggered.connect(
            lambda: self._show_cookie_dialog("pornhub")
        )
        
    def _show_cookie_dialog(self, platform: str) -> None:
        """显示Cookie管理对话框。
        
        Args:
            platform: 平台标识
        """
        dialog = CookieDialog(
            platform=platform,
            cookie_manager=self.cookie_manager,
            parent=self
        )
        
        if dialog.exec() == QDialog.Accepted:
            # 如果是Twitter，重新初始化下载器
            if platform == "twitter":
                self._init_twitter_downloader()
                
            # 如果是YouTube，重新初始化下载器
            elif platform == "youtube":
                self._init_youtube_downloader()
                
            # 如果是Pornhub，重新初始化下载器
            elif platform == "pornhub":
                self._init_pornhub_downloader()
                
            logger.info(f"{platform.title()}认证信息已更新")
            
    def _init_twitter_downloader(self) -> None:
        """初始化Twitter下载器。"""
        try:
            # 创建配置
            config = TwitterDownloaderConfig(
                save_dir=Path("downloads/twitter"),
                proxy="http://127.0.0.1:7890",
                timeout=30,
                max_retries=5,
                output_template="%(uploader)s/%(upload_date)s-%(title)s-%(id)s.%(ext)s"
            )
            
            # 创建下载器
            self.twitter_downloader = TwitterDownloader(
                config=config,
                progress_callback=lambda p, s: self.download_progress.emit(p, s),
                cookie_manager=self.cookie_manager
            )
            
            logger.info("Twitter下载器初始化成功")
            
        except Exception as e:
            logger.error(f"Twitter下载器初始化失败: {str(e)}")
            self.twitter_downloader = None
            
    def _init_youtube_downloader(self) -> None:
        """初始化YouTube下载器。"""
        try:
            # 创建配置
            config = YouTubeDownloaderConfig(
                save_dir=Path("downloads/youtube"),
                proxy="http://127.0.0.1:7890",
                timeout=30,
                max_retries=3,
                merge_output_format="mp4",
                output_template="%(uploader)s/%(title)s-%(id)s.%(ext)s"
            )
            
            # 创建下载器
            self.youtube_downloader = YouTubeDownloader(
                config=config,
                progress_callback=lambda p, s: self.download_progress.emit(p, s),
                cookie_manager=self.cookie_manager
            )
            
            logger.info("YouTube下载器初始化成功")
            
        except Exception as e:
            logger.error(f"初始化YouTube下载器失败: {e}")
            self.youtube_downloader = None
            
    def _init_pornhub_downloader(self) -> None:
        """初始化Pornhub下载器。"""
        try:
            # 创建配置
            config = PornhubDownloaderConfig(
                save_dir=Path("downloads/pornhub"),
                proxy="http://127.0.0.1:7890",
                timeout=30,
                max_retries=3,
                merge_output_format="mp4",
                output_template="%(uploader)s/%(title)s-%(id)s.%(ext)s"
            )
            
            # 创建下载器
            self.pornhub_downloader = PornhubDownloader(
                config=config,
                progress_callback=lambda p, s: self.download_progress.emit(float(p) / 100 if isinstance(p, (int, float)) else 0, str(s)),
                cookie_manager=self.cookie_manager
            )
            
            logger.info("Pornhub下载器初始化成功")
            
        except Exception as e:
            logger.error(f"Pornhub下载器初始化失败: {str(e)}")
            self.pornhub_downloader = None
            
    def _init_downloader(self) -> None:
        """初始化下载器。"""
        # 初始化下载器
        self.twitter_downloader = None
        self.youtube_downloader = None
        self.pornhub_downloader = None
        
        # 尝试初始化Twitter下载器
        self._init_twitter_downloader()
        
        # 尝试初始化YouTube下载器
        self._init_youtube_downloader()
        
        # 尝试初始化Pornhub下载器
        self._init_pornhub_downloader()
        
    def _connect_signals(self) -> None:
        """连接信号和槽。"""
        # 下载按钮信号
        self.download_btn.clicked.connect(self.start_download)
        self.channel_download_btn.clicked.connect(self.start_channel_download)
        self.cancel_btn.clicked.connect(self.cancel_download)
        
        # 进度信号
        self.download_progress.connect(self.update_progress)
        
    def _setup_logging(self) -> None:
        """设置日志处理。"""
        # 创建自定义的日志处理器
        class QTextEditHandler(logging.Handler):
            def __init__(self, signal):
                super().__init__()
                self.signal = signal
                
            def emit(self, record):
                msg = self.format(record)
                self.signal.emit(msg)
        
        # 获取根日志记录器
        root_logger = logging.getLogger()
        
        # 创建并添加自定义处理器
        qt_handler = QTextEditHandler(self.log_message)
        qt_handler.setFormatter(
            logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
        root_logger.addHandler(qt_handler)
        
    def _setup_ui(self) -> None:
        """设置UI界面。"""
        # 设置窗口标题和大小
        self.setWindowTitle("视频下载器")
        self.resize(800, 600)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        layout = QVBoxLayout(central_widget)
        
        # 创建输入区域
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入视频URL")
        self.download_btn = QPushButton("下载")
        self.channel_download_btn = QPushButton("下载频道")
        self.cancel_btn = QPushButton("取消")
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.download_btn)
        input_layout.addWidget(self.channel_download_btn)
        input_layout.addWidget(self.cancel_btn)
        layout.addLayout(input_layout)
        
        # 创建日志查看器
        self.log_viewer = LogHandler()
        layout.addWidget(self.log_viewer)
        
        # 创建进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
    @Slot()
    def start_download(self) -> None:
        """开始下载。"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "错误", "请输入视频URL")
            return
            
        # 获取下载器
        downloader = self._get_downloader(url)
        if not downloader:
            QMessageBox.warning(self, "错误", "不支持的URL格式")
            return
            
        # 创建异步下载线程
        thread = AsyncDownloader(
            self._async_download(url),
            parent=self
        )
        thread.finished.connect(self._handle_download_finished)
        thread.error.connect(self._handle_download_error)
        
        # 保存线程引用并启动
        self.active_downloaders.append(thread)
        thread.start()
        
        # 禁用下载按钮
        self.download_btn.setEnabled(False)
        self.channel_download_btn.setEnabled(False)
        
    @Slot()
    def start_channel_download(self) -> None:
        """开始下载频道/用户视频。"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "错误", "请输入频道/用户URL")
            return
            
        # 获取下载器
        downloader = self._get_downloader(url)
        if not downloader:
            QMessageBox.warning(self, "错误", "不支持的URL格式")
            return
            
        # 创建异步下载线程
        thread = AsyncDownloader(
            self._async_download_user(url),
            parent=self
        )
        thread.finished.connect(self._handle_channel_download_finished)
        thread.error.connect(self._handle_download_error)
        
        # 保存线程引用并启动
        self.active_downloaders.append(thread)
        thread.start()
        
        # 禁用下载按钮
        self.download_btn.setEnabled(False)
        self.channel_download_btn.setEnabled(False)
        
    def _handle_download_finished(self, result: Dict[str, Any]) -> None:
        """处理下载完成。
        
        Args:
            result: 下载结果
        """
        # 清理完成的下载线程
        self._cleanup_downloaders()
        
        # 启用下载按钮
        self.download_btn.setEnabled(True)
        self.channel_download_btn.setEnabled(True)
        
        # 重置进度条
        self.progress_bar.setValue(0)
        self.statusBar.showMessage("")
        
        # 显示结果
        if result.get('success'):
            QMessageBox.information(
                self,
                "下载完成",
                f"视频下载成功: {result.get('url', '')}"
            )
        else:
            QMessageBox.warning(
                self,
                "下载失败",
                f"视频下载失败: {result.get('message', '未知错误')}"
            )
            
    def _handle_channel_download_finished(self, result: Dict[str, Any]) -> None:
        """处理频道下载完成。
        
        Args:
            result: 下载结果
        """
        # 清理完成的下载线程
        self._cleanup_downloaders()
        
        # 启用下载按钮
        self.download_btn.setEnabled(True)
        self.channel_download_btn.setEnabled(True)
        
        # 重置进度条
        self.progress_bar.setValue(0)
        self.statusBar.showMessage("")
        
        # 显示结果
        if result.get('success'):
            QMessageBox.information(
                self,
                "下载完成",
                f"成功下载 {result.get('downloaded', 0)} 个视频，"
                f"失败 {result.get('failed', 0)} 个"
            )
        else:
            QMessageBox.warning(
                self,
                "下载失败",
                f"频道下载失败: {result.get('message', '未知错误')}"
            )
            
    def _handle_download_error(self, error: str) -> None:
        """处理下载错误。
        
        Args:
            error: 错误信息
        """
        # 清理完成的下载线程
        self._cleanup_downloaders()
        
        # 启用下载按钮
        self.download_btn.setEnabled(True)
        self.channel_download_btn.setEnabled(True)
        
        # 重置进度条
        self.progress_bar.setValue(0)
        self.statusBar.showMessage("")
        
        # 显示错误
        QMessageBox.warning(self, "下载失败", f"下载失败: {error}")
        
    def _cleanup_downloaders(self) -> None:
        """清理已完成的下载线程。"""
        self.active_downloaders = [
            d for d in self.active_downloaders
            if d.isRunning()
        ]
        
    def _get_downloader(self, url: str) -> Optional[BaseDownloader]:
        """获取适用的下载器。
        
        Args:
            url: 视频URL
            
        Returns:
            Optional[BaseDownloader]: 下载器实例
        """
        url = url.lower()
        
        if "twitter.com" in url:
            return self.twitter_downloader
        elif "youtube.com" in url or "youtu.be" in url:
            return self.youtube_downloader
        elif "pornhub.com" in url:
            return self.pornhub_downloader
            
        return None
        
    async def _async_download(self, url: str) -> Dict[str, Any]:
        """异步下载单个视频。
        
        Args:
            url: 视频URL
            
        Returns:
            Dict[str, Any]: 下载结果
        """
        downloader = self._get_downloader(url)
        if not downloader:
            return {
                'success': False,
                'message': "不支持的URL格式",
                'url': url
            }
            
        return await downloader.download(url)
        
    async def _async_download_user(self, url: str) -> Dict[str, Any]:
        """异步下载用户/频道视频。
        
        Args:
            url: 用户/频道URL
            
        Returns:
            Dict[str, Any]: 下载结果
        """
        downloader = self._get_downloader(url)
        if not downloader:
            return {
                'success': False,
                'message': "不支持的URL格式",
                'url': url
            }
            
        return await downloader.download_user(url)
        
    @Slot()
    def cancel_download(self) -> None:
        """取消下载。"""
        if hasattr(self, 'downloader'):
            self.downloader.cancel()
            logger.info("下载已取消")
            
    @Slot(float, str)
    def update_progress(self, progress: float, status: str) -> None:
        """更新进度条和状态。
        
        Args:
            progress: 进度值（0-1）
            status: 状态消息
        """
        try:
            # 更新进度条
            if progress is not None:
                progress_value = int(progress * 100)
                self.progress_bar.setValue(progress_value)
            
            # 更新状态栏
            if status:
                # 限制状态消息长度
                status = status[:100] + '...' if len(status) > 100 else status
                self.statusBar.showMessage(status)
                
        except Exception as e:
            logger.error(f"更新进度失败: {str(e)}")

    def _on_theme_changed(self, checked: bool):
        """主题切换回调。
        
        Args:
            checked: 是否选中
        """
        self.theme_manager.switch_dark_mode(checked)

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 