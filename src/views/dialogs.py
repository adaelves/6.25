"""对话框模块"""

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QListWidget
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve

class MacDialog(QDialog):
    """Mac风格弹窗基类"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setup_ui()
        
        # 添加显示动画
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.setDuration(300)
    
    def setup_ui(self):
        """设置UI布局"""
        pass
    
    def showEvent(self, event):
        """显示事件处理"""
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.start()
        super().showEvent(event)

class HistoryDialog(MacDialog):
    """历史记录弹窗"""
    
    def setup_ui(self):
        container = QWidget()
        container.setObjectName("Container")
        container.setStyleSheet(
            "#Container { background: white; border-radius: 10px; }"
        )
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("历史记录")
        title.setProperty("title", True)
        
        self.list = QListWidget()
        
        layout.addWidget(title)
        layout.addWidget(self.list)
        
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(container)
        self.resize(400, 500)

class DownloadDialog(MacDialog):
    """下载管理弹窗"""
    
    def setup_ui(self):
        container = QWidget()
        container.setObjectName("Container")
        container.setStyleSheet(
            "#Container { background: white; border-radius: 10px; }"
        )
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("下载管理")
        title.setProperty("title", True)
        
        self.file_label = QLabel("正在下载: example_video.mp4")
        self.progress = QProgressBar()
        self.progress.setValue(0)
        
        layout.addWidget(title)
        layout.addWidget(self.file_label)
        layout.addWidget(self.progress)
        
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(container)
        self.resize(500, 300) 