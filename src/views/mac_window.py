"""Mac风格窗口基类"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget,
    QListWidget, QListWidgetItem, QTabWidget,
    QGraphicsDropShadowEffect, QToolBar, QLineEdit,
    QCheckBox, QComboBox, QSlider, QProxyStyle, QStyle,
    QGraphicsOpacityEffect, QApplication
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QPropertyAnimation, QEasingCurve,
    QRect, QTimer, QMimeData, QParallelAnimationGroup,
    QSequentialAnimationGroup, Property, QEvent, QCoreApplication,
    QSettings
)
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QPen,
    QBrush, QLinearGradient, QFontDatabase, QIcon,
    QPalette, QTransform, QDrag, QCloseEvent
)

def create_color(hex_color, alpha=255):
    """创建颜色，支持透明度"""
    color = QColor(hex_color)
    color.setAlpha(alpha)
    return color

class ThemeManager:
    """主题管理类"""
    _instance = None
    
    # 颜色定义
    COLORS = {
        'light': {
            'background': '#F5F5F7',
            'foreground': '#1C1C1E',
            'surface': '#FFFFFF',
            'border': '#D8D8D8',
            'accent': '#007AFF',
        },
        'dark': {
            'background': '#1E1E1E',
            'foreground': '#FFFFFF',
            'surface': '#2C2C2E',
            'border': '#3C3C3E',
            'accent': '#0A84FF',
        }
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化主题管理器"""
        self.settings = QSettings("YourCompany", "AppName")
        self.app = QApplication.instance()
        
        # 加载主题设置
        self.theme_mode = self.settings.value("theme/mode", "auto")
        self.font_scale = float(self.settings.value("theme/font_scale", 1.0))
        
        # 初始化调色板
        self._setup_palettes()
        
        # 应用初始主题
        self.apply_theme()
    
    def _setup_palettes(self):
        """设置明暗主题调色板"""
        # 亮色主题
        self.light_palette = QPalette()
        self.light_palette.setColor(QPalette.Window, create_color(self.COLORS['light']['background']))
        self.light_palette.setColor(QPalette.WindowText, create_color(self.COLORS['light']['foreground']))
        self.light_palette.setColor(QPalette.Base, create_color(self.COLORS['light']['surface']))
        self.light_palette.setColor(QPalette.AlternateBase, create_color(self.COLORS['light']['background']))
        self.light_palette.setColor(QPalette.Text, create_color(self.COLORS['light']['foreground']))
        self.light_palette.setColor(QPalette.Button, create_color(self.COLORS['light']['surface']))
        self.light_palette.setColor(QPalette.ButtonText, create_color(self.COLORS['light']['foreground']))
        self.light_palette.setColor(QPalette.Highlight, create_color(self.COLORS['light']['accent']))
        self.light_palette.setColor(QPalette.HighlightedText, create_color('#FFFFFF'))
        self.light_palette.setColor(QPalette.PlaceholderText, create_color(self.COLORS['light']['foreground'], 128))
        
        # 暗色主题
        self.dark_palette = QPalette()
        self.dark_palette.setColor(QPalette.Window, create_color(self.COLORS['dark']['background']))
        self.dark_palette.setColor(QPalette.WindowText, create_color(self.COLORS['dark']['foreground']))
        self.dark_palette.setColor(QPalette.Base, create_color(self.COLORS['dark']['surface']))
        self.dark_palette.setColor(QPalette.AlternateBase, create_color(self.COLORS['dark']['background']))
        self.dark_palette.setColor(QPalette.Text, create_color(self.COLORS['dark']['foreground']))
        self.dark_palette.setColor(QPalette.Button, create_color(self.COLORS['dark']['surface']))
        self.dark_palette.setColor(QPalette.ButtonText, create_color(self.COLORS['dark']['foreground']))
        self.dark_palette.setColor(QPalette.Highlight, create_color(self.COLORS['dark']['accent']))
        self.dark_palette.setColor(QPalette.HighlightedText, create_color('#FFFFFF'))
        self.dark_palette.setColor(QPalette.PlaceholderText, create_color(self.COLORS['dark']['foreground'], 128))
    
    def is_dark_mode(self):
        """检查是否应该使用暗色主题"""
        if self.theme_mode == "light":
            return False
        elif self.theme_mode == "dark":
            return True
        else:  # auto
            # 检测系统主题
            return self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    
    def set_theme_mode(self, mode):
        """设置主题模式"""
        if mode in ["light", "dark", "auto"]:
            self.theme_mode = mode
            self.settings.setValue("theme/mode", mode)
            self.apply_theme()
    
    def set_font_scale(self, scale):
        """设置字体缩放"""
        self.font_scale = float(scale)
        self.settings.setValue("theme/font_scale", scale)
        self.apply_font_scale()
    
    def apply_theme(self):
        """应用主题设置"""
        palette = self.dark_palette if self.is_dark_mode() else self.light_palette
        self.app.setPalette(palette)
    
    def apply_font_scale(self):
        """应用字体缩放"""
        font = self.app.font()
        font.setPointSize(int(13 * self.font_scale))
        self.app.setFont(font)
    
    def get_colors(self):
        """获取当前主题的颜色方案"""
        theme = 'dark' if self.is_dark_mode() else 'light'
        return self.COLORS[theme]

class FontManager:
    """字体管理类"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化字体系统"""
        self.font_families = []
        self._load_system_fonts()
        
        # 设置默认字体
        self.default_font = QFont()
        self.default_font.setFamily(self._get_system_font())
        self.default_font.setPointSize(13)
        
        # 获取主题管理器
        self.theme_manager = ThemeManager()
    
    def _load_system_fonts(self):
        """加载系统字体"""
        # 添加首选字体
        self.font_families = [
            "SF Pro Display",  # macOS
            "San Francisco",   # macOS
            "-apple-system",   # macOS fallback
            "Segoe UI",       # Windows
            "Roboto",         # Android/Linux
            "Helvetica Neue", # macOS older
            "Helvetica",      # General
            "Arial",          # General
            "sans-serif"      # Final fallback
        ]
    
    def _get_system_font(self):
        """获取系统最适合的字体"""
        db = QFontDatabase()
        available_fonts = db.families()
        
        # 查找第一个可用的字体
        for font in self.font_families:
            if font in available_fonts:
                return font
        
        # 如果都不可用，返回系统默认无衬线字体
        return self.default_font.defaultFamily()
    
    def get_font(self, size=13, weight=QFont.Normal):
        """获取字体实例"""
        font = QFont(self.default_font)
        # 应用字体缩放
        font.setPointSize(int(size * self.theme_manager.font_scale))
        font.setWeight(weight)
        return font
    
    @property
    def font_family_css(self):
        """获取字体族CSS"""
        return "font-family: " + ", ".join(f'"{f}"' for f in self.font_families) + ";"

class WindowControlButton(QPushButton):
    """macOS风格窗口控制按钮"""
    def __init__(self, color, hover_color, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)  # 标准大小
        self.color = QColor(color)
        self.hover_color = QColor(hover_color)
        self.is_hovered = False
        self.is_pressed = False
        
        # 设置鼠标跟踪以捕获hover事件
        self.setMouseTracking(True)
    
    def enterEvent(self, event):
        if self.parent().isActiveWindow():
            self.is_hovered = True
            self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_pressed = True
            self.update()
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_pressed = False
            self.update()
        super().mouseReleaseEvent(event)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制按钮背景
        path = QPainterPath()
        path.addEllipse(1, 1, 10, 10)
        
        if not self.parent().isActiveWindow():
            # 窗口未激活时显示灰色
            color = QColor(200, 200, 200)
        elif self.is_pressed:
            color = self.hover_color.darker(110)
        elif self.is_hovered:
            color = self.hover_color
        else:
            color = self.color
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(path)
        
        # 在hover状态下绘制符号
        if self.is_hovered and self.parent().isActiveWindow():
            painter.setPen(QPen(QColor(0, 0, 0, 80), 1.1, Qt.SolidLine, Qt.RoundCap))
            
            # 根据按钮类型绘制不同的符号
            if self.objectName() == "CloseBtn":
                # 绘制关闭符号(×)
                painter.drawLine(4, 4, 8, 8)
                painter.drawLine(4, 8, 8, 4)
            elif self.objectName() == "MinimizeBtn":
                # 绘制最小化符号(-)
                painter.drawLine(4, 6, 8, 6)
            elif self.objectName() == "ZoomBtn":
                # 绘制最大化符号(+)
                painter.drawLine(4, 6, 8, 6)
                painter.drawLine(6, 4, 6, 8)

class TitleBar(QWidget):
    """macOS风格标题栏"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)  # 标准高度
        self.setObjectName("TitleBar")
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)
        
        # 窗口控制按钮组
        btn_container = QWidget()
        btn_container.setFixedWidth(70)  # 按钮组固定宽度
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)  # 标准间距
        
        # 创建控制按钮
        self.close_btn = WindowControlButton("#FF5F56", "#FF4D4F")
        self.close_btn.setObjectName("CloseBtn")
        
        self.minimize_btn = WindowControlButton("#FFBD2E", "#FFB117")
        self.minimize_btn.setObjectName("MinimizeBtn")
        
        self.zoom_btn = WindowControlButton("#27C93F", "#24B238")
        self.zoom_btn.setObjectName("ZoomBtn")
        
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
        spacer.setFixedWidth(70)  # 与按钮组等宽
        layout.addWidget(spacer)
    
    def update_title(self, title):
        """更新窗口标题"""
        self.title_label.setText(title)

class MacLineEdit(QLineEdit):
    """macOS风格输入框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MacLineEdit")
        
        # 设置清除按钮
        self.setClearButtonEnabled(True)
        
        # 设置占位符样式
        self.setPlaceholderText("")
        
        # 设置固定高度
        self.setFixedHeight(32)  # macOS标准输入框高度

class MacButton(QPushButton):
    """macOS风格按钮"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("MacButton")
        self.setCursor(Qt.PointingHandCursor)
        
        # 设置固定高度
        self.setFixedHeight(32)  # macOS标准按钮高度
        
        # 设置最小宽度
        self.setMinimumWidth(80)

class MacCheckBox(QCheckBox):
    """macOS Big Sur风格复选框"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("MacCheckBox")
        
        # 设置文字间距
        self.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
            }
        """)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 获取复选框矩形区域
        checkbox_rect = QRect(0, 0, 16, 16)
        checkbox_rect.moveCenter(QPoint(8, self.height() // 2))
        
        # 绘制边框或填充背景
        if self.isChecked():
            # 选中状态
            painter.setBrush(QColor("#007AFF"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(checkbox_rect, 3, 3)
            
            # 绘制勾选标记
            painter.setPen(QPen(Qt.white, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(checkbox_rect.left() + 4, checkbox_rect.top() + 8,
                           checkbox_rect.left() + 7, checkbox_rect.top() + 11)
            painter.drawLine(checkbox_rect.left() + 7, checkbox_rect.top() + 11,
                           checkbox_rect.right() - 3, checkbox_rect.top() + 5)
        else:
            # 未选中状态
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#D0D0D0"), 1))
            painter.drawRoundedRect(checkbox_rect, 3, 3)
        
        # 绘制文本
        text_rect = self.rect().adjusted(24, 0, 0, 0)
        painter.setPen(QPen(QColor("#1C1C1E")))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.text())

class MacComboBoxStyle(QProxyStyle):
    """macOS风格下拉菜单样式"""
    def __init__(self):
        super().__init__()
        
    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.CE_ComboBoxLabel:
            if not option.currentText:
                return
                
            rect = option.rect.adjusted(8, 0, -24, 0)  # 左侧8px padding，右侧预留箭头空间
            painter.setPen(QPen(QColor("#1C1C1E")))
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, option.currentText)
            return
            
        elif element == QStyle.CE_ComboBoxArrow:
            # 绘制SF Symbols风格的下拉箭头
            rect = option.rect
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 箭头颜色
            if not option.state & QStyle.State_Enabled:
                painter.setPen(QPen(QColor("#A0A0A0"), 1.5))
            else:
                painter.setPen(QPen(QColor("#1C1C1E"), 1.5))
            
            # 绘制箭头
            center = rect.center()
            path = QPainterPath()
            path.moveTo(center.x() - 4, center.y() - 2)
            path.lineTo(center.x(), center.y() + 2)
            path.lineTo(center.x() + 4, center.y() - 2)
            painter.drawPath(path)
            return
            
        super().drawControl(element, option, painter, widget)

class MacComboBox(QComboBox):
    """macOS风格下拉菜单"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MacComboBox")
        self.setStyle(MacComboBoxStyle())
        
        # 设置固定高度
        self.setFixedHeight(32)
        
        # 设置下拉菜单样式
        self.setStyleSheet("""
            QComboBox {
                border: 1px solid #D0D0D0;
                border-radius: 6px;
                padding-left: 8px;
                padding-right: 24px;
                background: white;
                min-width: 120px;
            }
            QComboBox:hover {
                border-color: #B8B8B8;
            }
            QComboBox:focus {
                border-color: #007AFF;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #D0D0D0;
                border-radius: 6px;
                background: white;
                selection-background-color: #007AFF;
                selection-color: white;
            }
        """)

class MacSlider(QSlider):
    """macOS风格滑块"""
    def __init__(self, orientation=Qt.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setObjectName("MacSlider")
        
        # 设置最小高度
        if orientation == Qt.Horizontal:
            self.setMinimumHeight(20)  # 为滑块手柄预留足够空间
        
        # 设置页步长
        self.setPageStep(10)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 计算轨道区域
        track_rect = self.rect()
        if self.orientation() == Qt.Horizontal:
            track_rect.setHeight(4)
            track_rect.moveCenter(self.rect().center())
        else:
            track_rect.setWidth(4)
            track_rect.moveCenter(self.rect().center())
        
        # 绘制轨道背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#E5E5E5"))
        painter.drawRoundedRect(track_rect, 2, 2)
        
        # 计算已完成部分的区域
        progress = (self.value() - self.minimum()) / (self.maximum() - self.minimum())
        if self.orientation() == Qt.Horizontal:
            progress_rect = QRect(track_rect.left(), track_rect.top(),
                                int(track_rect.width() * progress), track_rect.height())
        else:
            progress_rect = QRect(track_rect.left(), track_rect.bottom() - int(track_rect.height() * progress),
                                track_rect.width(), int(track_rect.height() * progress))
        
        # 绘制已完成部分
        painter.setBrush(QColor("#007AFF"))
        painter.drawRoundedRect(progress_rect, 2, 2)
        
        # 绘制滑块手柄
        handle_size = 16
        if self.orientation() == Qt.Horizontal:
            handle_x = int(track_rect.left() + (track_rect.width() - handle_size) * progress)
            handle_y = track_rect.center().y() - handle_size // 2
        else:
            handle_x = track_rect.center().x() - handle_size // 2
            handle_y = int(track_rect.bottom() - (track_rect.height() - handle_size) * progress - handle_size)
        
        # 绘制手柄阴影
        shadow_color = QColor(0, 0, 0, 20)
        painter.setBrush(shadow_color)
        painter.drawEllipse(handle_x + 1, handle_y + 1, handle_size, handle_size)
        
        # 绘制手柄
        painter.setBrush(QColor("white"))
        painter.setPen(QPen(QColor("#D0D0D0"), 1))
        painter.drawEllipse(handle_x, handle_y, handle_size, handle_size)

class AnimatedButton(MacButton):
    """带动画效果的按钮"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._setup_animations()
    
    def _setup_animations(self):
        # 缩放动画
        self.scale_animation = QPropertyAnimation(self, b"scale_factor")
        self.scale_animation.setDuration(100)
        self.scale_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # 初始化缩放因子
        self.scale_factor = 1.0
    
    def get_scale_factor(self):
        return self._scale_factor
    
    def set_scale_factor(self, factor):
        self._scale_factor = factor
        self.setTransform(QTransform().scale(factor, factor))
    
    scale_factor = Property(float, get_scale_factor, set_scale_factor)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 点击时缩小
            self.scale_animation.setStartValue(1.0)
            self.scale_animation.setEndValue(0.9)
            self.scale_animation.start()
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 释放时恢复
            self.scale_animation.setStartValue(0.9)
            self.scale_animation.setEndValue(1.0)
            self.scale_animation.start()
        super().mouseReleaseEvent(event)

class NavigationItem(QWidget):
    """带动画效果的导航项"""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setObjectName("NavigationItem")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        
        self.label = QLabel(text)
        layout.addWidget(self.label)
        
        # 背景色动画
        self.color_animation = QPropertyAnimation(self, b"background_color")
        self.color_animation.setDuration(200)
        self.color_animation.setEasingCurve(QEasingCurve.InOutCubic)
        
        self._background_color = QColor("#FFFFFF")
        self.setAutoFillBackground(True)
    
    def get_background_color(self):
        return self._background_color
    
    def set_background_color(self, color):
        self._background_color = color
        palette = self.palette()
        palette.setColor(QPalette.Window, color)
        self.setPalette(palette)
    
    background_color = Property(QColor, get_background_color, set_background_color)
    
    def setSelected(self, selected):
        if selected:
            self.color_animation.setStartValue(QColor("#FFFFFF"))
            self.color_animation.setEndValue(QColor("#E8E8E8"))
        else:
            self.color_animation.setStartValue(QColor("#E8E8E8"))
            self.color_animation.setEndValue(QColor("#FFFFFF"))
        self.color_animation.start()

class DropArea(QFrame):
    """带高亮效果的拖放区域"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropArea")
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.StyledPanel)
        
        # 默认样式
        self.setStyleSheet("""
            #DropArea {
                border: 1px solid #D8D8D8;
                border-radius: 8px;
                background: white;
                min-height: 100px;
            }
            #DropArea[dragActive="true"] {
                border: 2px dashed #007AFF;
                background: #F0F9FF;
            }
        """)
        
        # 提示文本
        layout = QVBoxLayout(self)
        self.label = QLabel("拖放文件到这里")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        
        self.setProperty("dragActive", False)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
    
    def dragLeaveEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
    
    def dropEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            urls = event.mimeData().urls()
            # 处理拖放的文件...

class MacWindow(QMainWindow):
    """Mac风格窗口基类"""
    def __init__(self, title="", min_size=(800, 500)):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(*min_size)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 初始化主题管理器和字体管理器
        self.theme_manager = ThemeManager()
        self.font_manager = FontManager()
        
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
        self.apply_mac_style()
        
        # 窗口拖动相关
        self.drag_pos = None
    
    def apply_mac_style(self):
        """应用macOS风格样式表"""
        colors = self.theme_manager.get_colors()
        style = f"""
            * {{
                {self.font_manager.font_family_css}
            }}
            
            #MainWidget {{
                background: {colors['background']};
                border-radius: 10px;
            }}
            
            #TitleBar {{
                background: {colors['surface']};
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }}
            
            #TitleLabel {{
                color: {colors['foreground']};
                font-size: {13 * self.theme_manager.font_scale}px;
                margin: 0 10px;
            }}
            
            #MainToolBar {{
                background: {colors['background']};
                border: none;
                spacing: 10px;
                padding: 5px 10px;
            }}
            
            #MainToolBar QToolButton {{
                background: transparent;
                border: none;
                color: {colors['foreground']};
                padding: 5px 10px;
                border-radius: 4px;
            }}
            
            #MainToolBar QToolButton:hover {{
                background: {colors['surface']};
            }}
            
            #ContentWidget {{
                background: {colors['surface']};
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }}
            
            #MacLineEdit {{
                background-color: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                padding: 8px;
                color: {colors['foreground']};
                font-size: {13 * self.theme_manager.font_scale}px;
                selection-background-color: {colors['accent']};
            }}
            
            #MacLineEdit:focus {{
                border-color: {colors['accent']};
            }}
            
            #MacLineEdit:hover {{
                border-color: #B8B8B8;
            }}
            
            #MacButton {{
                background-color: {colors['accent']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: {13 * self.theme_manager.font_scale}px;
                font-weight: 500;
            }}
            
            #MacButton:hover {{
                background-color: {colors['accent']};
                opacity: 0.9;
            }}
            
            #MacButton:pressed {{
                background-color: {colors['accent']};
                opacity: 0.8;
            }}
            
            #MacButton:disabled {{
                background-color: {colors['surface']};
                color: {colors['foreground']};
                opacity: 0.5;
            }}
            
            #MacCheckBox {{
                color: #1C1C1E;
                font-size: 13px;
            }}
            
            #MacCheckBox:disabled {{
                color: #A0A0A0;
            }}
            
            #MacSlider {{
                margin: 8px 0;
            }}
            
            #NavigationItem {{
                border-radius: 6px;
                padding: 8px;
            }}
            
            #NavigationItem:hover {{
                background: #F5F5F5;
            }}
            
            #NavigationItem[selected="true"] {{
                background: #E8E8E8;
            }}
        """
        self.setStyleSheet(style)
        
        # 应用字体
        self.title_bar.title_label.setFont(
            self.font_manager.get_font(13, QFont.Medium)
        )
    
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
            self.apply_mac_style()
        super().changeEvent(event) 