"""对话框组件模块"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QDialogButtonBox, QWidget, QFrame
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from .widgets.mac_controls import MacButton

class MacDialog(QDialog):
    """macOS风格对话框基类"""
    def __init__(self, parent=None, title="", message=""):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        
        # 设置固定大小
        self.setFixedSize(400, 200)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 内容容器
        self.content = QWidget()
        self.content.setObjectName("DialogContent")
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(20)
        
        # 标题和消息
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("DialogTitle")
            content_layout.addWidget(title_label)
        
        if message:
            message_label = QLabel(message)
            message_label.setObjectName("DialogMessage")
            message_label.setWordWrap(True)
            content_layout.addWidget(message_label)
        
        # 按钮区域
        button_container = QWidget()
        button_container.setObjectName("DialogButtonContainer")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 20, 0, 0)
        button_layout.setSpacing(10)
        
        # 创建按钮
        self.button_box = QDialogButtonBox()
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)
        
        content_layout.addWidget(button_container)
        layout.addWidget(self.content)
    
    def paintEvent(self, event):
        """绘制对话框背景和阴影"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制半透明背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 128))
        
        # 绘制对话框主体
        content_path = QPainterPath()
        content_path.addRoundedRect(0, 0, self.width(), self.height(), 10, 10)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(245, 245, 247))
        painter.drawPath(content_path)

class MessageDialog(MacDialog):
    """消息对话框"""
    def __init__(self, parent=None, title="", message="", buttons=QDialogButtonBox.Ok):
        super().__init__(parent, title, message)
        
        # 添加按钮
        ok_button = MacButton("确定")
        ok_button.setObjectName("DialogOkButton")
        self.button_box.addButton(ok_button, QDialogButtonBox.AcceptRole)
        
        if buttons & QDialogButtonBox.Cancel:
            cancel_button = MacButton("取消")
            cancel_button.setObjectName("DialogCancelButton")
            self.button_box.addButton(cancel_button, QDialogButtonBox.RejectRole)

class ProgressDialog(MacDialog):
    """进度对话框"""
    def __init__(self, parent=None, title="", message=""):
        super().__init__(parent, title, message)
        
        # 进度条
        self.progress_bar = QFrame()
        self.progress_bar.setObjectName("DialogProgressBar")
        self.progress_bar.setFixedHeight(4)
        
        # 进度动画
        self.progress_animation = QPropertyAnimation(self.progress_bar, b"geometry")
        self.progress_animation.setDuration(1000)
        self.progress_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 添加到布局
        self.content.layout().insertWidget(
            self.content.layout().count() - 1,  # 在按钮区域之前插入
            self.progress_bar
        )
    
    def set_progress(self, value):
        """设置进度值（0-100）"""
        width = int(self.width() * value / 100)
        self.progress_animation.setStartValue(self.progress_bar.geometry())
        self.progress_animation.setEndValue(QRect(0, self.progress_bar.y(), width, self.progress_bar.height()))
        self.progress_animation.start()

class SettingsDialog(MacDialog):
    """设置对话框"""
    def __init__(self, parent=None, settings=None):
        super().__init__(parent, "设置", "")
        self.settings = settings
        
        # TODO: 添加设置项
        # - 下载路径
        # - 最大并发数
        # - 主题模式
        # - 字体缩放
        # - 代理设置
        
        # 添加按钮
        apply_button = MacButton("应用")
        apply_button.setObjectName("DialogApplyButton")
        self.button_box.addButton(apply_button, QDialogButtonBox.ApplyRole)
        
        cancel_button = MacButton("取消")
        cancel_button.setObjectName("DialogCancelButton")
        self.button_box.addButton(cancel_button, QDialogButtonBox.RejectRole)
        
        # 连接信号
        apply_button.clicked.connect(self.apply_settings)
    
    def apply_settings(self):
        """应用设置"""
        # TODO: 保存设置
        pass 