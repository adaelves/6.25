"""主窗口模块。

该模块实现了应用程序的主窗口界面。
"""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QProgressBar, QLabel,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Slot, Signal

from src.plugins.youtube import YouTubeDownloader

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """应用程序主窗口。
    
    提供视频下载的主要界面，包含URL输入、下载按钮和进度显示。
    
    Attributes:
        url_input: QLineEdit, URL输入框
        download_btn: QPushButton, 下载按钮
        progress_bar: QProgressBar, 下载进度条
    """
    
    download_started = Signal(str)  # 下载开始信号
    download_progress = Signal(float)  # 下载进度信号
    download_finished = Signal(bool)  # 下载完成信号
    
    def __init__(self) -> None:
        """初始化主窗口。"""
        super().__init__()
        
        self.setWindowTitle("视频下载器")
        self.setMinimumSize(600, 200)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # URL输入区域
        url_layout = QHBoxLayout()
        url_label = QLabel("视频URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入YouTube视频URL")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        
        # 下载按钮
        self.download_btn = QPushButton("下载")
        self.download_btn.clicked.connect(self._on_download_clicked)
        url_layout.addWidget(self.download_btn)
        
        # 添加URL布局
        layout.addLayout(url_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
        # 添加伸缩器
        layout.addStretch()
        
        # 初始化下载器
        self.downloader: Optional[YouTubeDownloader] = None
        
        # 连接信号
        self.download_progress.connect(self._update_progress)
        self.download_finished.connect(self._on_download_finished)
        
    @Slot()
    def _on_download_clicked(self) -> None:
        """处理下载按钮点击事件。"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "错误", "请输入视频URL")
            return
            
        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择保存位置",
            str(Path.home() / "Downloads" / "video.mp4"),
            "视频文件 (*.mp4)"
        )
        
        if not file_path:
            return
            
        try:
            # 初始化下载器
            self.downloader = YouTubeDownloader()
            
            # 获取视频信息
            info = self.downloader.get_video_info(url)
            
            # 更新状态
            self.status_label.setText(f"正在下载: {info['title']}")
            self.download_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            
            # 开始下载
            success = self.downloader.download(url, Path(file_path))
            self.download_finished.emit(success)
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            QMessageBox.critical(self, "错误", f"下载失败: {e}")
            self.download_finished.emit(False)
            
    @Slot(float)
    def _update_progress(self, progress: float) -> None:
        """更新进度条。
        
        Args:
            progress: 下载进度（0-100）
        """
        self.progress_bar.setValue(int(progress))
        
    @Slot(bool)
    def _on_download_finished(self, success: bool) -> None:
        """处理下载完成事件。
        
        Args:
            success: 下载是否成功
        """
        self.download_btn.setEnabled(True)
        if success:
            self.status_label.setText("下载完成")
            QMessageBox.information(self, "完成", "视频下载完成！")
        else:
            self.status_label.setText("下载失败")
            
    def closeEvent(self, event) -> None:
        """处理窗口关闭事件。"""
        if self.downloader is not None:
            # TODO: 处理正在进行的下载
            pass
        event.accept() 