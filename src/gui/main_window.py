#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频下载器主窗口模块。

实现主要的GUI界面和交互逻辑。
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from typing import Optional, Dict
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
from PySide6.QtCore import Qt, Slot, Signal

from src.core.downloader import BaseDownloader
from src.utils.logger import get_logger
from src.plugins.youtube.downloader import YouTubeDownloader
from src.plugins.youtube.config import YouTubeDownloaderConfig
from src.plugins.twitter.downloader import TwitterDownloader
from src.plugins.twitter.config import TwitterDownloaderConfig
from src.utils.cookie_manager import CookieManager
from src.gui.cookie_dialog import CookieDialog

# 创建日志记录器
logger = get_logger("gui")

class AuthDialog(QDialog):
    """认证对话框。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Twitter认证")
        self.setModal(True)
        
        layout = QFormLayout(self)
        
        # 认证方式选择
        self.auth_method = QComboBox()
        self.auth_method.addItems([
            "浏览器Cookies",
            "手动输入Cookies",
            "用户名密码(不推荐)"
        ])
        layout.addRow("认证方式:", self.auth_method)
        
        # 浏览器选择和路径
        self.browser_group = QWidget()
        browser_layout = QFormLayout(self.browser_group)
        self.browser = QComboBox()
        self.browser.addItems([
            "chrome",
            "firefox",
            "edge",
            "brave",
            "chromium",
            "opera",
            "vivaldi",
            "safari"
        ])
        self.browser_path = QLineEdit()
        self.browser_path.setPlaceholderText("浏览器数据目录路径（可选）")
        self.select_path_btn = QPushButton("选择目录")
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.browser_path)
        path_layout.addWidget(self.select_path_btn)
        browser_layout.addRow("浏览器:", self.browser)
        browser_layout.addRow("数据目录:", path_layout)
        layout.addRow(self.browser_group)
        
        # Cookies输入
        self.cookies_group = QWidget()
        cookies_layout = QVBoxLayout(self.cookies_group)
        self.cookies_input = QTextEdit()
        self.cookies_input.setPlaceholderText(
            "请输入Cookies，格式如下：\n"
            "名称1=值1; 名称2=值2; ...\n"
            "或者\n"
            "{\n"
            '    "名称1": "值1",\n'
            '    "名称2": "值2"\n'
            "}"
        )
        self.cookies_input.setMinimumHeight(100)
        cookies_layout.addWidget(QLabel("Cookies:"))
        cookies_layout.addWidget(self.cookies_input)
        layout.addRow(self.cookies_group)
        
        # 用户名密码输入
        self.credentials_group = QWidget()
        credentials_layout = QFormLayout(self.credentials_group)
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        credentials_layout.addRow("用户名:", self.username)
        credentials_layout.addRow("密码:", self.password)
        layout.addRow(self.credentials_group)
        
        # 确定取消按钮
        buttons = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        buttons.addWidget(self.ok_button)
        buttons.addWidget(self.cancel_button)
        layout.addRow(buttons)
        
        # 连接信号
        self.auth_method.currentIndexChanged.connect(self._toggle_inputs)
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.select_path_btn.clicked.connect(self._select_browser_path)
        
        # 初始化UI状态
        self._toggle_inputs(0)
        
    def _select_browser_path(self) -> None:
        """选择浏览器数据目录。"""
        path = QFileDialog.getExistingDirectory(
            self,
            "选择浏览器数据目录",
            str(Path.home())
        )
        if path:
            self.browser_path.setText(path)
            
    def _toggle_inputs(self, index: int) -> None:
        """切换输入控件的可用状态。"""
        # 隐藏所有组件
        self.browser_group.setVisible(False)
        self.cookies_group.setVisible(False)
        self.credentials_group.setVisible(False)
        
        # 根据选择显示对应组件
        if index == 0:  # 浏览器Cookies
            self.browser_group.setVisible(True)
        elif index == 1:  # 手动输入Cookies
            self.cookies_group.setVisible(True)
        else:  # 用户名密码
            self.credentials_group.setVisible(True)
            
    def _parse_cookies(self, cookies_str: str) -> Dict[str, str]:
        """解析Cookies字符串。
        
        Args:
            cookies_str: Cookies字符串
            
        Returns:
            Dict[str, str]: Cookies字典
        """
        cookies = {}
        try:
            # 尝试解析JSON格式
            if cookies_str.strip().startswith("{"):
                import json
                cookies = json.loads(cookies_str)
            else:
                # 解析 cookie 字符串格式
                for cookie in cookies_str.split(";"):
                    if "=" in cookie:
                        name, value = cookie.strip().split("=", 1)
                        cookies[name.strip()] = value.strip()
        except Exception as e:
            logger.error(f"解析Cookies失败: {e}")
            raise ValueError("Cookies格式无效，请检查输入")
            
        return cookies
        
    def get_auth_info(self) -> Dict:
        """获取认证信息。"""
        auth_method = self.auth_method.currentIndex()
        
        if auth_method == 0:  # 浏览器Cookies
            browser_path = self.browser_path.text().strip()
            return {
                "browser_profile": self.browser.currentText(),
                "browser_path": browser_path if browser_path else None
            }
        elif auth_method == 1:  # 手动输入Cookies
            cookies_str = self.cookies_input.toPlainText().strip()
            if not cookies_str:
                raise ValueError("请输入Cookies")
            return {
                "cookies": self._parse_cookies(cookies_str)
            }
        else:  # 用户名密码
            username = self.username.text().strip()
            password = self.password.text()
            if not username or not password:
                raise ValueError("用户名和密码不能为空")
            return {
                "username": username,
                "password": password
            }

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

class MainWindow(QMainWindow):
    """下载器主窗口。"""
    
    # 自定义信号
    download_progress = Signal(float, str)  # 下载进度信号
    log_message = Signal(str)  # 日志消息信号
    
    def __init__(self):
        """初始化主窗口。"""
        super().__init__()
        
        # 设置窗口属性
        self.setWindowTitle("视频下载器")
        self.resize(800, 600)
        
        # 设置代理
        self.proxy = "http://127.0.0.1:7890"
        
        # 创建Cookie管理器
        self.cookie_manager = CookieManager()
        
        # 初始化UI
        self._setup_ui()
        
        # 连接信号
        self._connect_signals()
        
        # 初始化下载器
        self._init_downloader()
        
        # 设置日志处理
        self._setup_logging()
        
    def _setup_ui(self) -> None:
        """设置UI界面。"""
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # URL输入区域
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入视频/图片URL或Twitter用户主页URL")
        url_layout.addWidget(self.url_input)
        
        # 下载按钮区域
        button_layout = QHBoxLayout()
        self.download_btn = QPushButton("下载")
        self.channel_download_btn = QPushButton("下载全部媒体")
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.channel_download_btn)
        button_layout.addWidget(self.cancel_btn)
        
        # 下载选项区域
        options_layout = QHBoxLayout()
        self.max_tweets_label = QLabel("最大推文数:")
        self.max_tweets_input = QLineEdit("100")
        self.max_tweets_input.setFixedWidth(80)
        self.max_workers_label = QLabel("并发数:")
        self.max_workers_input = QLineEdit("3")
        self.max_workers_input.setFixedWidth(80)
        options_layout.addWidget(self.max_tweets_label)
        options_layout.addWidget(self.max_tweets_input)
        options_layout.addWidget(self.max_workers_label)
        options_layout.addWidget(self.max_workers_input)
        options_layout.addStretch()
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        
        # 日志区域
        self.log_viewer = LogHandler()
        
        # 添加所有组件到主布局
        main_layout.addLayout(url_layout)
        main_layout.addLayout(button_layout)
        main_layout.addLayout(options_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.log_viewer)
        
        # 创建菜单栏
        self._create_menu_bar()
        
        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
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
            
    def _init_downloader(self) -> None:
        """初始化下载器。"""
        # 初始化下载器
        self.twitter_downloader = None
        self.youtube_downloader = None
        
        # 尝试初始化Twitter下载器
        self._init_twitter_downloader()
        
        # 尝试初始化YouTube下载器
        self._init_youtube_downloader()
        
    def _connect_signals(self) -> None:
        """连接信号和槽。"""
        # 下载按钮信号
        self.download_btn.clicked.connect(self.start_download)
        self.channel_download_btn.clicked.connect(self.start_channel_download)
        self.cancel_btn.clicked.connect(self.cancel_download)
        
        # 进度信号
        self.download_progress.connect(self.update_progress)
        self.log_message.connect(self.log_viewer.append_log)
        
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
        
    @Slot()
    def start_download(self) -> None:
        """开始下载。"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "错误", "请输入下载链接")
            return
            
        # 获取下载器
        downloader = self._get_downloader(url)
        if not downloader:
            QMessageBox.warning(self, "错误", "不支持的URL格式")
            return
            
        try:
            # 更新UI状态
            self.download_btn.setEnabled(False)
            self.channel_download_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("正在下载...")
            
            # 开始下载
            logger.info(f"开始下载: {url}")
            result = downloader.download(url)
            
            if result['success']:
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("下载完成")
                QMessageBox.information(
                    self,
                    "下载完成",
                    f"成功下载 {result.get('media_count', 0)} 个媒体文件"
                )
            else:
                QMessageBox.warning(
                    self,
                    "下载失败",
                    result.get('message', '未知错误')
                )
                
        except Exception as e:
            logger.error(f"下载出错: {e}")
            QMessageBox.critical(self, "错误", f"下载失败: {str(e)}")
            
        finally:
            # 恢复UI状态
            self.download_btn.setEnabled(True)
            self.channel_download_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("%p%")
            
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
        
    @Slot()
    def start_channel_download(self) -> None:
        """开始频道下载。"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "错误", "请输入Twitter用户主页URL")
            return
            
        try:
            # 获取下载器
            downloader = self._get_downloader(url)
            if not isinstance(downloader, TwitterDownloader):
                QMessageBox.warning(self, "错误", "该功能仅支持Twitter用户主页")
                return
                
            # 获取下载参数
            try:
                max_tweets = int(self.max_tweets_input.text())
                max_workers = int(self.max_workers_input.text())
                if max_tweets <= 0 or max_workers <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "错误", "请输入有效的数字")
                return
                
            # 更新UI状态
            self.download_btn.setEnabled(False)
            self.channel_download_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("正在获取推文列表...")
            
            # 开始下载
            try:
                result = downloader.download_channel(
                    url,
                    max_count=max_tweets
                )
                
                if result['success']:
                    self.progress_bar.setValue(100)
                    self.progress_bar.setFormat("下载完成")
                    
                    # 构建结果消息
                    message = f"成功下载 {result.get('media_count', 0)} 个媒体文件"
                    if result.get('failed_count', 0) > 0:
                        message += f"\n失败 {result['failed_count']} 个"
                        
                    QMessageBox.information(
                        self,
                        "下载完成",
                        message
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "下载失败",
                        result.get('message', '未知错误')
                    )
                    
            except Exception as e:
                logger.error(f"频道下载失败: {e}")
                QMessageBox.critical(self, "错误", f"下载失败: {str(e)}")
                
        except Exception as e:
            logger.error(f"初始化下载器失败: {e}")
            QMessageBox.critical(self, "错误", f"初始化下载器失败: {str(e)}")
            
        finally:
            # 恢复UI状态
            self.download_btn.setEnabled(True)
            self.channel_download_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("%p%")
            
    def closeEvent(self, event) -> None:
        """窗口关闭事件处理。
        
        Args:
            event: 关闭事件
        """
        try:
            # 取消正在进行的下载
            if hasattr(self, 'downloader'):
                self.downloader.cancel()
                
            # 保存配置等
            logger.info("应用程序关闭")
            event.accept()
            
        except Exception as e:
            logger.error(f"处理窗口关闭事件失败: {e}")
            event.accept()

    def _get_downloader(self, url: str) -> Optional[BaseDownloader]:
        """根据URL获取对应的下载器。
        
        Args:
            url: 下载URL
            
        Returns:
            Optional[BaseDownloader]: 下载器实例或None
        """
        url = url.lower()
        if "youtube.com" in url or "youtu.be" in url:
            return self.youtube_downloader
        elif "twitter.com" in url or "x.com" in url:
            if not self.twitter_downloader:
                self._init_twitter_downloader()
            return self.twitter_downloader
        return None

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 