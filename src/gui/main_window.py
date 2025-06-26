#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频下载器主窗口模块。

实现主要的GUI界面和交互逻辑。
"""

import sys
import logging
from typing import Optional
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
    QMessageBox
)
from PySide6.QtCore import Qt, Slot, Signal

from src.core.downloader import BaseDownloader
from src.utils.logger import get_logger
from src.plugins.youtube.downloader import YouTubeDownloader
from src.plugins.youtube.config import YouTubeDownloaderConfig

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
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # URL输入区域
        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入视频URL")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.download_button = QPushButton("开始下载")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        # 日志显示区域
        self.log_display = LogHandler()
        
        # 添加所有控件到主布局
        main_layout.addLayout(url_layout)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.log_display)
        
    def _connect_signals(self) -> None:
        """连接信号和槽。"""
        # 按钮点击
        self.download_button.clicked.connect(self.start_download)
        self.cancel_button.clicked.connect(self.cancel_download)
        
        # 自定义信号
        self.download_progress.connect(self.update_progress)
        self.log_message.connect(self.log_display.append_log)
        
    def _init_downloader(self) -> None:
        """初始化下载器。"""
        # 创建下载配置
        config = YouTubeDownloaderConfig(
            save_dir=Path("downloads"),
            proxy="http://127.0.0.1:7890",
            max_height=1080,
            prefer_quality="1080p",
            merge_output_format="mp4"
        )
        
        # 创建下载器
        self.downloader = YouTubeDownloader(
            config=config
        )
        
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
        
    def _progress_callback(self, progress: float, status: str) -> None:
        """下载进度回调函数。
        
        Args:
            progress: 进度值（0-1）
            status: 状态消息
        """
        self.download_progress.emit(progress, status)
        
    @Slot()
    def start_download(self) -> None:
        """开始下载。"""
        url = self.url_input.text().strip()
        
        if not url:
            QMessageBox.warning(self, "错误", "请输入视频URL")
            return
            
        # 更新UI状态
        self.download_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.url_input.setEnabled(False)
        self.progress_bar.setValue(0)
        
        try:
            # 开始下载
            logger.info(f"开始下载: {url}")
            success = self.downloader.download(url)
            
            if success:
                logger.info("下载完成")
                QMessageBox.information(self, "完成", "下载完成")
            else:
                logger.error("下载失败")
                QMessageBox.warning(self, "错误", "下载失败")
                
        except Exception as e:
            logger.error(f"下载出错: {e}")
            QMessageBox.critical(self, "错误", str(e))
            
        finally:
            # 恢复UI状态
            self.download_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.url_input.setEnabled(True)
            
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
        # 更新进度条
        progress_value = int(progress * 100)
        self.progress_bar.setValue(progress_value)
        
        # 更新状态栏
        self.statusBar().showMessage(status)
        
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