"""主窗口模块"""

import sys
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QStackedWidget, QToolBar,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QApplication
)
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve,
    QTimer, QEvent, QSettings
)
from PySide6.QtGui import (
    QColor, QPainter, QPainterPath, QPen,
    QBrush, QFontDatabase, QIcon, QPalette
)

from .widgets.title_bar import TitleBar
from core.models import AppSettings

class MainWindow(QMainWindow):
    """主窗口类"""
    def __init__(self, title="视频下载器", min_size=(800, 500)):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(*min_size)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 加载设置
        self.settings = QSettings("YourCompany", "VideoDownloader")
        self.app_settings = AppSettings(
            download_path=self.settings.value("download_path", os.path.expanduser("~/Downloads")),
            max_concurrent=int(self.settings.value("max_concurrent", 3)),
            theme_mode=self.settings.value("theme_mode", "auto"),
            font_scale=float(self.settings.value("font_scale", 1.0)),
            proxy_enabled=bool(self.settings.value("proxy_enabled", False)),
            proxy_address=self.settings.value("proxy_address", None)
        )
        
        # 窗口动画效果
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(300)
        self.opacity_animation.setEasingCurve(QEasingCurve.InOutCubic)
        
        # 显示时的淡入动画
        self.opacity_effect.setOpacity(0)
        QTimer.singleShot(0, self._show_animation)
        
        # 主窗口容器（实现圆角）
        self.main_widget = QWidget()
        self.main_widget.setObjectName("MainWidget")
        main_layout = QVBoxLayout(self.main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 标题栏
        self.title_bar = TitleBar(self)
        self.title_bar.update_title(title)
        main_layout.addWidget(self.title_bar)
        
        # 连接窗口控制按钮信号
        self.title_bar.close_btn.clicked.connect(self.close)
        self.title_bar.minimize_btn.clicked.connect(self.showMinimized)
        self.title_bar.zoom_btn.clicked.connect(self.toggle_maximize)
        
        # 工具栏
        self.toolbar = QToolBar()
        self.toolbar.setObjectName("MainToolBar")
        self.toolbar.setMovable(False)
        main_layout.addWidget(self.toolbar)
        
        # 内容区域
        self.content_widget = QWidget()
        self.content_widget.setObjectName("ContentWidget")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(30, 30, 30, 30)
        self.content_layout.setSpacing(20)
        
        main_layout.addWidget(self.content_widget)
        
        self.setCentralWidget(self.main_widget)
        self.add_window_shadow()
        self.load_styles()
        
        # 窗口拖动相关
        self.drag_pos = None
    
    def load_styles(self):
        """加载样式表"""
        style_file = os.path.join(os.path.dirname(__file__), "..", "resources", "styles.qss")
        if os.path.exists(style_file):
            with open(style_file, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
    
    def add_window_shadow(self):
        """添加窗口阴影效果"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 0)
        self.main_widget.setGraphicsEffect(shadow)
    
    def paintEvent(self, event):
        """重写绘制事件，确保QPainter正常工作"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景
        painter.fillRect(self.rect(), Qt.transparent)
        
        # 绘制窗口边框
        if not self.isMaximized():
            path = QPainterPath()
            path.addRoundedRect(0, 0, self.width(), self.height(), 10, 10)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(245, 245, 247))
            painter.drawPath(path)
    
    def mousePressEvent(self, event):
        """仅允许通过标题栏拖动窗口"""
        if event.button() == Qt.LeftButton:
            title_bar_rect = self.title_bar.geometry()
            if title_bar_rect.contains(event.pos()):
                self.drag_pos = event.globalPosition().toPoint()
    
    def mouseMoveEvent(self, event):
        """处理窗口拖动"""
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()
    
    def mouseReleaseEvent(self, event):
        """重置拖动状态"""
        self.drag_pos = None
    
    def toggle_maximize(self):
        """切换最大化状态"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized() 
    
    def _show_animation(self):
        """窗口显示动画"""
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.start()
    
    def closeEvent(self, event):
        """窗口关闭动画"""
        if not hasattr(self, '_closing'):
            self._closing = True
            self.opacity_animation.setStartValue(1.0)
            self.opacity_animation.setEndValue(0.0)
            self.opacity_animation.finished.connect(self._handle_close)
            self.opacity_animation.start()
            event.ignore()
        else:
            super().closeEvent(event)
    
    def _handle_close(self):
        """动画结束后真正关闭窗口"""
        self.close()  # 这会再次触发closeEvent，但这次会直接关闭 
    
    def changeEvent(self, event):
        """处理窗口状态改变事件"""
        if event.type() == QEvent.PaletteChange:
            # 系统主题改变时更新样式
            self.load_styles()
        super().changeEvent(event)

def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("VideoDownloader")
    app.setOrganizationName("YourCompany")
    app.setApplicationVersion("1.0.0")
    
    # 加载字体
    font_dir = os.path.join(os.path.dirname(__file__), "..", "resources", "fonts")
    if os.path.exists(font_dir):
        for font_file in os.listdir(font_dir):
            if font_file.endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(font_dir, font_file))
    
    # 创建并显示主窗口
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec()) 