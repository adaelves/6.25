"""主窗口模块"""

import os
from typing import Optional, Dict
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QStackedWidget,
    QPushButton, QFrame, QSizePolicy
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QSettings, QPropertyAnimation,
    QEasingCurve, QRect
)
from PySide6.QtGui import (
    QFont, QFontDatabase, QColor, QPainter, QPainterPath,
    QBrush, QPen, QIcon
)

from .widgets.title_bar import TitleBar
from core.theme_manager import ThemeManager

class BlurEffect(QWidget):
    """毛玻璃效果组件"""
    def __init__(self, parent=None, radius=10, opacity=0.8):
        super().__init__(parent)
        self.radius = radius
        self.opacity = opacity
        
        # 设置背景透明
        self.setAttribute(Qt.WA_TranslucentBackground)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 创建圆角路径
        path = QPainterPath()
        path.addRoundedRect(self.rect(), self.radius, self.radius)
        
        # 设置画刷
        if self.parent().theme_manager.is_dark_mode():
            brush = QBrush(QColor(44, 44, 46, int(255 * self.opacity)))
        else:
            brush = QBrush(QColor(245, 245, 247, int(255 * self.opacity)))
        
        # 绘制背景
        painter.setClipPath(path)
        painter.fillPath(path, brush)

class SidebarItem(QListWidgetItem):
    """侧边栏导航项"""
    def __init__(self, symbol: str, text: str, size: QSize = QSize(180, 36)):
        super().__init__()
        self.symbol = symbol
        
        # 设置文本
        self.setText(f"  {symbol}  {text}")
        
        # 设置字体
        font = QFont("SF Pro", 13)
        self.setFont(font)
        
        # 设置大小
        self.setSizeHint(size)
        
        # 设置对齐方式
        self.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

class MainWindow(QMainWindow):
    """主窗口类"""
    def __init__(self):
        super().__init__()
        self.init_window()
        self.setup_ui()
        self.load_settings()
        
    def init_window(self):
        """初始化窗口"""
        # 基本设置
        self.setWindowTitle("视频下载器")
        self.setMinimumSize(900, 600)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 创建主题管理器
        self.theme_manager = ThemeManager(self)
        self.theme_manager.theme_changed.connect(self.on_theme_changed)
        
        # 创建设置管理器
        self.settings = QSettings("YourCompany", "VideoDownloader")
        
        # 窗口拖动相关
        self.drag_pos = None
        
    def setup_ui(self):
        """设置UI"""
        # 主布局
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 标题栏
        self.title_bar = self.setup_title_bar()
        main_layout.addWidget(self.title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # 侧边栏
        self.sidebar = self.setup_sidebar()
        content_layout.addWidget(self.sidebar)
        
        # 主内容区
        self.content_stack = self.setup_content_stack()
        content_layout.addWidget(self.content_stack)
        
        main_layout.addWidget(content_widget)
        self.setCentralWidget(main_widget)
        
    def setup_title_bar(self) -> TitleBar:
        """设置标题栏"""
        title_bar = TitleBar(self)
        title_bar.update_title(self.windowTitle())
        
        # 连接窗口控制按钮信号
        title_bar.close_btn.clicked.connect(self.close)
        title_bar.minimize_btn.clicked.connect(self.showMinimized)
        title_bar.zoom_btn.clicked.connect(self.toggle_maximize)
        
        return title_bar
    
    def setup_sidebar(self) -> QWidget:
        """设置侧边栏"""
        sidebar = QWidget()
        sidebar.setObjectName("SideBar")
        sidebar.setFixedWidth(220)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        # 导航列表
        nav_list = QListWidget()
        nav_list.setObjectName("NavList")
        nav_list.setFrameShape(QFrame.NoFrame)
        nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 添加导航项
        nav_items = [
            ("􀎞", "下载"),  # house.fill
            ("􀈎", "正在下载"),  # arrow.down.circle
            ("􀋊", "已完成"),  # checkmark.circle
            ("􀍡", "订阅"),  # star.fill
            ("􀍪", "设置")  # gear
        ]
        
        for symbol, text in nav_items:
            item = SidebarItem(symbol, text)
            nav_list.addItem(item)
        
        # 选中第一项
        nav_list.setCurrentRow(0)
        
        # 连接信号
        nav_list.currentRowChanged.connect(self.on_nav_changed)
        
        layout.addWidget(nav_list)
        layout.addStretch()
        
        return sidebar
    
    def setup_content_stack(self) -> QStackedWidget:
        """设置内容区域"""
        stack = QStackedWidget()
        stack.setObjectName("ContentStack")
        
        # 添加页面
        pages = [
            self.create_download_page(),
            self.create_downloading_page(),
            self.create_completed_page(),
            self.create_subscription_page(),
            self.create_settings_page()
        ]
        
        for page in pages:
            stack.addWidget(page)
        
        return stack
    
    def create_download_page(self) -> QWidget:
        """创建下载页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        
        # TODO: 实现下载页面UI
        layout.addWidget(QLabel("下载页面"))
        
        return page
    
    def create_downloading_page(self) -> QWidget:
        """创建正在下载页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        
        # TODO: 实现正在下载页面UI
        layout.addWidget(QLabel("正在下载页面"))
        
        return page
    
    def create_completed_page(self) -> QWidget:
        """创建已完成页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        
        # TODO: 实现已完成页面UI
        layout.addWidget(QLabel("已完成页面"))
        
        return page
    
    def create_subscription_page(self) -> QWidget:
        """创建订阅页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        
        # TODO: 实现订阅页面UI
        layout.addWidget(QLabel("订阅页面"))
        
        return page
    
    def create_settings_page(self) -> QWidget:
        """创建设置页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        
        # TODO: 实现设置页面UI
        layout.addWidget(QLabel("设置页面"))
        
        return page
    
    def load_settings(self):
        """加载窗口设置"""
        # 恢复窗口位置和大小
        geometry = self.settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        # 恢复窗口状态
        state = self.settings.value("window/state")
        if state:
            self.restoreState(state)
    
    def save_settings(self):
        """保存窗口设置"""
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/state", self.saveState())
    
    def on_theme_changed(self, theme_name: str):
        """处理主题改变"""
        # 更新UI元素
        self.update()
    
    def on_nav_changed(self, index: int):
        """处理导航切换"""
        # 切换内容页面
        self.content_stack.setCurrentIndex(index)
    
    def toggle_maximize(self):
        """切换最大化状态"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
    
    def mousePressEvent(self, event):
        """处理鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            if self.title_bar.geometry().contains(event.pos()):
                self.drag_pos = event.globalPosition().toPoint()
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件"""
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()
    
    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件"""
        self.drag_pos = None
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        self.save_settings()
        super().closeEvent(event)
    
    def paintEvent(self, event):
        """绘制窗口背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 创建圆角路径
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 10, 10)
        
        # 设置画刷
        if self.theme_manager.is_dark_mode():
            brush = QBrush(QColor(30, 30, 30))
        else:
            brush = QBrush(QColor(245, 245, 247))
        
        # 绘制背景
        painter.fillPath(path, brush) 