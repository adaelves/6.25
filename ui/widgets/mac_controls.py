"""Mac风格控件模块"""

from PySide6.QtWidgets import (
    QPushButton, QLineEdit, QCheckBox, QComboBox,
    QSlider, QProxyStyle, QStyle, QWidget,
    QVBoxLayout, QLabel, QFrame
)
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve,
    Property, QPoint
)
from PySide6.QtGui import (
    QColor, QPainter, QPainterPath, QPen,
    QBrush, QTransform
)

class WindowControlButton(QPushButton):
    """macOS风格窗口控制按钮"""
    def __init__(self, color, hover_color, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)  # macOS标准大小
        self.color = QColor(color)
        self.hover_color = QColor(hover_color)
        self.is_hovered = False
        self.is_pressed = False
        
        # 设置鼠标跟踪以捕获hover事件
        self.setMouseTracking(True)
        
        # 缩放动画
        self.scale_animation = QPropertyAnimation(self, b"scale_factor")
        self.scale_animation.setDuration(100)
        self.scale_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._scale_factor = 1.0
    
    def get_scale_factor(self):
        return self._scale_factor
    
    def set_scale_factor(self, factor):
        self._scale_factor = factor
        self.setTransform(QTransform().scale(factor, factor))
    
    scale_factor = Property(float, get_scale_factor, set_scale_factor)
    
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
            # 点击时缩小
            self.scale_animation.setStartValue(1.0)
            self.scale_animation.setEndValue(0.9)
            self.scale_animation.start()
            self.update()
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_pressed = False
            # 释放时恢复
            self.scale_animation.setStartValue(0.9)
            self.scale_animation.setEndValue(1.0)
            self.scale_animation.start()
            self.update()
        super().mouseReleaseEvent(event)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 计算按钮中心点和半径
        center = self.rect().center()
        radius = 7  # 直径14px的一半
        
        # 绘制按钮背景
        path = QPainterPath()
        path.addEllipse(center, radius, radius)
        
        if not self.parent().isActiveWindow():
            # 窗口未激活时显示灰色
            color = QColor(200, 200, 200)
        elif self.is_pressed:
            # 按下时显示更深的颜色
            color = self.hover_color.darker(120)
        elif self.is_hovered:
            # 悬停时显示高亮颜色
            color = self.hover_color
        else:
            # 正常状态
            color = self.color
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPath(path)
        
        # 在hover状态下绘制符号
        if self.is_hovered and self.parent().isActiveWindow():
            painter.setPen(QPen(QColor(0, 0, 0, 80), 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            
            # 根据按钮类型绘制不同的符号
            if self.objectName() == "CloseBtn":
                # 绘制关闭符号(×)
                painter.drawLine(center.x() - 3, center.y() - 3,
                               center.x() + 3, center.y() + 3)
                painter.drawLine(center.x() - 3, center.y() + 3,
                               center.x() + 3, center.y() - 3)
            elif self.objectName() == "MinimizeBtn":
                # 绘制最小化符号(-)
                painter.drawLine(center.x() - 3, center.y(),
                               center.x() + 3, center.y())
            elif self.objectName() == "ZoomBtn":
                # 绘制最大化符号(+)
                painter.drawLine(center.x() - 3, center.y(),
                               center.x() + 3, center.y())
                painter.drawLine(center.x(), center.y() - 3,
                               center.x(), center.y() + 3)

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
        
        layout = QVBoxLayout(self)
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