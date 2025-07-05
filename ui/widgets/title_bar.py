"""标题栏组件模块"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from .mac_controls import WindowControlButton

class TitleBar(QWidget):
    """macOS风格标题栏"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)  # macOS标准高度
        self.setObjectName("TitleBar")
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)  # macOS标准边距
        layout.setSpacing(0)
        
        # 窗口控制按钮组
        btn_container = QWidget()
        btn_container.setFixedWidth(66)  # 按钮组固定宽度 (14px * 3 + 8px * 3)
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)  # macOS标准间距
        
        # 创建控制按钮
        self.close_btn = WindowControlButton("#FF5F56", "#FF4D4F")
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setToolTip("关闭")
        
        self.minimize_btn = WindowControlButton("#FFBD2E", "#FFB117")
        self.minimize_btn.setObjectName("MinimizeBtn")
        self.minimize_btn.setToolTip("最小化")
        
        self.zoom_btn = WindowControlButton("#27C93F", "#24B238")
        self.zoom_btn.setObjectName("ZoomBtn")
        self.zoom_btn.setToolTip("缩放")
        
        btn_layout.addWidget(self.close_btn)
        btn_layout.addWidget(self.minimize_btn)
        btn_layout.addWidget(self.zoom_btn)
        
        # 标题文本
        self.title_label = QLabel()
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        
        # 添加到主布局
        layout.addWidget(btn_container)
        layout.addWidget(self.title_label)
        
        # 右侧预留空间
        spacer = QWidget()
        spacer.setFixedWidth(66)  # 与按钮组等宽
        layout.addWidget(spacer)
    
    def update_title(self, title):
        """更新窗口标题"""
        self.title_label.setText(title) 