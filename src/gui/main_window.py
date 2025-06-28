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
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from typing import Optional, Dict, Any
from pathlib import Path

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
    QStatusBar
)
from PySide6.QtCore import Qt, Slot, Signal, QTimer, QThread

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

class MainWindow(QMainWindow):
    """下载器主窗口。"""
    
    # 自定义信号
    download_progress = Signal(float, str)  # 下载进度信号
    log_message = Signal(str)  # 日志消息信号
    
    def __init__(self):
        super().__init__()
        
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
            # 加载配置
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
            # 创建YouTube配置
            config = YouTubeDownloaderConfig(
                save_dir=Path("downloads"),
                proxy=self.proxy,
                max_height=1080,
                prefer_quality="1080p",
                merge_output_format="mp4"
            )
            
            # 创建YouTube下载器
            self.youtube_downloader = YouTubeDownloader(
                config=config,
                cookie_manager=self.cookie_manager
            )
            
            # 设置进度回调
            self.youtube_downloader.progress_callback = lambda p, s: self.download_progress.emit(p, s)
            
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
                max_height=1080,
                min_height=480,
                merge_output_format="mp4",
                output_template="%(uploader)s/%(title)s-%(id)s.%(ext)s",
                max_downloads=50
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

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 
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
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from typing import Optional, Dict, Any
from pathlib import Path

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
    QStatusBar
)
from PySide6.QtCore import Qt, Slot, Signal, QTimer, QThread

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

class MainWindow(QMainWindow):
    """下载器主窗口。"""
    
    # 自定义信号
    download_progress = Signal(float, str)  # 下载进度信号
    log_message = Signal(str)  # 日志消息信号
    
    def __init__(self):
        super().__init__()
        
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
            # 加载配置
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
            # 创建YouTube配置
            config = YouTubeDownloaderConfig(
                save_dir=Path("downloads"),
                proxy=self.proxy,
                max_height=1080,
                prefer_quality="1080p",
                merge_output_format="mp4"
            )
            
            # 创建YouTube下载器
            self.youtube_downloader = YouTubeDownloader(
                config=config,
                cookie_manager=self.cookie_manager
            )
            
            # 设置进度回调
            self.youtube_downloader.progress_callback = lambda p, s: self.download_progress.emit(p, s)
            
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
                max_height=1080,
                min_height=480,
                merge_output_format="mp4",
                output_template="%(uploader)s/%(title)s-%(id)s.%(ext)s",
                max_downloads=50
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

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 
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
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from typing import Optional, Dict, Any
from pathlib import Path

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
    QStatusBar
)
from PySide6.QtCore import Qt, Slot, Signal, QTimer, QThread

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

class MainWindow(QMainWindow):
    """下载器主窗口。"""
    
    # 自定义信号
    download_progress = Signal(float, str)  # 下载进度信号
    log_message = Signal(str)  # 日志消息信号
    
    def __init__(self):
        super().__init__()
        
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
            # 加载配置
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
            # 创建YouTube配置
            config = YouTubeDownloaderConfig(
                save_dir=Path("downloads"),
                proxy=self.proxy,
                max_height=1080,
                prefer_quality="1080p",
                merge_output_format="mp4"
            )
            
            # 创建YouTube下载器
            self.youtube_downloader = YouTubeDownloader(
                config=config,
                cookie_manager=self.cookie_manager
            )
            
            # 设置进度回调
            self.youtube_downloader.progress_callback = lambda p, s: self.download_progress.emit(p, s)
            
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
                max_height=1080,
                min_height=480,
                merge_output_format="mp4",
                output_template="%(uploader)s/%(title)s-%(id)s.%(ext)s",
                max_downloads=50
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

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 