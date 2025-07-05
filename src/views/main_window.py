"""主窗口模块"""

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QStackedWidget,
    QListWidget, QListWidgetItem, QCheckBox, QComboBox, QSpinBox,
    QDialog, QScrollArea, QTabWidget, QProgressBar, QSplitter,
    QTreeWidget, QTreeWidgetItem, QMenuBar, QMenu,
    QStatusBar, QStyle, QDockWidget, QFormLayout, QFileDialog,
    QMessageBox, QGridLayout, QToolButton, QGroupBox, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QSize, Signal, Slot, QThread, QModelIndex, QPoint, QRect, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QIcon, QFont, QColor, QPalette, QBrush, QPixmap, QImage, QPainter,
    QPen, QPainterPath, QWindow, QAction
)

from .mac_window import MacWindow

class MacStyleTitleBar(QWidget):
    """Mac风格的标题栏，包含窗口控制按钮"""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.init_ui(title)
    
    def init_ui(self, title):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(5)
        
        # 窗口控制按钮
        self.close_btn = QPushButton()
        self.minimize_btn = QPushButton()
        self.maximize_btn = QPushButton()
        
        # 设置按钮样式
        for btn in [self.close_btn, self.minimize_btn, self.maximize_btn]:
            btn.setFixedSize(12, 12)
            btn.setStyleSheet("border-radius: 6px;")
        
        # 关闭按钮
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5F56;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #E04E45;
            }
        """)
        
        # 最小化按钮
        self.minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFBD2E;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #E0A528;
            }
        """)
        
        # 最大化按钮
        self.maximize_btn.setStyleSheet("""
            QPushButton {
                background-color: #27C93F;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #22B037;
            }
        """)
        
        # 添加到布局
        layout.addWidget(self.close_btn)
        layout.addWidget(self.minimize_btn)
        layout.addWidget(self.maximize_btn)
        layout.addStretch()
        
        # 添加标题
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #333; font-size: 13px;")
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        layout.addStretch()
        
        self.setLayout(layout)

class MacDialogTitleBar(QWidget):
    """Mac风格对话框标题栏"""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("DialogTitleBar")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        
        # 关闭按钮
        self.close_btn = QPushButton()
        self.close_btn.setObjectName("DialogCloseBtn")
        self.close_btn.setFixedSize(12, 12)
        
        # 标题
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.close_btn)
        layout.addStretch()
        layout.addWidget(title_label)
        layout.addStretch()

class MacDialog(QDialog):
    """Mac风格对话框基类"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setup_ui()
        self.apply_style()
        
        # 窗口拖动相关
        self.drag_pos = None
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 内容区域
        self.content = QWidget()
        self.content.setObjectName("DialogContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(self.content)
    
    def apply_style(self):
        self.setStyleSheet("""
            #DialogContent {
                background: white;
                border-radius: 10px;
                border: 1px solid #E1E1E1;
            }
            #DialogTitleBar {
                background: #E8E8E8;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border-bottom: 1px solid #D1D1D1;
            }
            #DialogCloseBtn {
                background: #FF5F57;
                border: none;
                border-radius: 6px;
            }
            #DialogCloseBtn:hover {
                background: #FF4D4F;
            }
        """)
    
    def set_title(self, title):
        """设置对话框标题并添加标题栏"""
        self.setWindowTitle(title)
        title_bar = MacDialogTitleBar(title, self)
        title_bar.close_btn.clicked.connect(self.close)
        self.content_layout.insertWidget(0, title_bar)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.y() < 32:
            self.drag_pos = event.globalPosition().toPoint()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()
    
    def mouseReleaseEvent(self, event):
        self.drag_pos = None

class CreatorMonitorDialog(MacDialog):
    """创作者监控对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 500)
        self.set_title("创作者监控")
        self.setup_creator_ui()
    
    def setup_creator_ui(self):
        # 顶部控制区域
        control_layout = QHBoxLayout()
        
        add_btn = QPushButton("添加创作者")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self.add_creator)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("SecondaryBtn")
        
        control_layout.addWidget(add_btn)
        control_layout.addWidget(refresh_btn)
        control_layout.addStretch()
        
        # 创作者列表
        self.creator_tree = QTreeWidget()
        self.creator_tree.setHeaderLabels(["创作者", "平台", "最新视频", "更新时间"])
        self.creator_tree.setObjectName("CreatorTree")
        
        self.content_layout.addLayout(control_layout)
        self.content_layout.addWidget(self.creator_tree)
    
    def add_creator(self):
        """添加创作者"""
        QMessageBox.information(self, "提示", "添加创作者功能将在后续版本中实现")

class HistoryDialog(MacDialog):
    """历史记录对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 500)
        self.set_title("历史记录")
        self.setup_history_ui()
    
    def setup_history_ui(self):
        self.history_list = QListWidget()
        self.history_list.setObjectName("HistoryList")
        
        clear_btn = QPushButton("清空历史记录")
        clear_btn.setObjectName("SecondaryBtn")
        clear_btn.clicked.connect(self.clear_history)
        
        self.content_layout.addWidget(self.history_list)
        self.content_layout.addWidget(clear_btn, alignment=Qt.AlignRight)
    
    def clear_history(self):
        """清空历史记录"""
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有历史记录吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.history_list.clear()

class PreferencesDialog(MacDialog):
    """首选项对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 500)
        self.set_title("首选项")
        self.setup_preferences_ui()
    
    def setup_preferences_ui(self):
        tabs = QTabWidget()
        tabs.setObjectName("PrefTabs")
        
        # 常规设置
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        # 播放列表选项
        playlist_group = QFrame()
        playlist_group.setObjectName("PrefGroup")
        playlist_layout = QVBoxLayout(playlist_group)
        
        playlist_title = QLabel("播放列表选项")
        playlist_title.setObjectName("GroupTitle")
        
        options = [
            "为播放列表和频道创建子目录",
            "在文件名中添加序号",
            "跳过重复视频（实验）",
            "生成.m3u播放列表文件"
        ]
        
        playlist_layout.addWidget(playlist_title)
        for text in options:
            cb = QCheckBox(text)
            cb.setObjectName("PrefCheckbox")
            playlist_layout.addWidget(cb)
        
        # 媒体处理选项
        media_group = QFrame()
        media_group.setObjectName("PrefGroup")
        media_layout = QVBoxLayout(media_group)
        
        media_title = QLabel("媒体处理")
        media_title.setObjectName("GroupTitle")
        
        media_options = [
            "嵌入字幕到视频",
            "自动添加标签信息",
            "导入到媒体库"
        ]
        
        media_layout.addWidget(media_title)
        for text in media_options:
            cb = QCheckBox(text)
            cb.setObjectName("PrefCheckbox")
            media_layout.addWidget(cb)
        
        general_layout.addWidget(playlist_group)
        general_layout.addWidget(media_group)
        general_layout.addStretch()
        
        # 连接设置
        connection_tab = QWidget()
        connection_layout = QVBoxLayout(connection_tab)
        
        # 下载目录设置
        dir_group = QFrame()
        dir_group.setObjectName("PrefGroup")
        dir_layout = QFormLayout(dir_group)
        
        self.download_dir_input = QLineEdit()
        self.download_dir_input.setText("./downloads")
        self.download_dir_input.setReadOnly(True)
        
        change_dir_btn = QPushButton("更改")
        change_dir_btn.setObjectName("SecondaryBtn")
        change_dir_btn.clicked.connect(self.change_download_dir)
        
        dir_btn_layout = QHBoxLayout()
        dir_btn_layout.addWidget(self.download_dir_input)
        dir_btn_layout.addWidget(change_dir_btn)
        
        dir_layout.addRow("下载目录:", dir_btn_layout)
        
        # 代理设置
        proxy_group = QFrame()
        proxy_group.setObjectName("PrefGroup")
        proxy_layout = QFormLayout(proxy_group)
        
        self.proxy_check = QCheckBox("使用代理")
        self.proxy_input = QLineEdit()
        self.proxy_input.setText("127.0.0.1:7890")
        self.proxy_input.setEnabled(False)
        
        self.proxy_check.toggled.connect(self.proxy_input.setEnabled)
        
        proxy_layout.addRow("代理设置:", self.proxy_check)
        proxy_layout.addRow("", self.proxy_input)
        
        # 下载设置
        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel("下载强度:"))
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 8)
        self.thread_spin.setValue(3)
        thread_layout.addStretch()
        
        warning = QLabel("高强度可能导致临时IP封禁")
        warning.setObjectName("WarningLabel")
        
        connection_layout.addWidget(dir_group)
        connection_layout.addWidget(proxy_group)
        connection_layout.addLayout(thread_layout)
        connection_layout.addWidget(warning)
        connection_layout.addStretch()
        
        tabs.addTab(general_tab, "常规")
        tabs.addTab(connection_tab, "连接")
        
        self.content_layout.addWidget(tabs)
    
    def change_download_dir(self):
        """更改下载目录"""
        directory = QFileDialog.getExistingDirectory(
            self, "选择下载目录",
            self.download_dir_input.text(),
            QFileDialog.ShowDirsOnly
        )
        if directory:
            self.download_dir_input.setText(directory)

class MainWindow(MacWindow):
    """视频下载器主窗口"""
    def __init__(self):
        super().__init__("Universal Video Downloader")
        self.setup_toolbar()
        self.setup_main_ui()
        self.setup_dialogs()
    
    def setup_toolbar(self):
        """设置工具栏"""
        # 创作者监控
        creator_btn = QToolButton()
        creator_btn.setText("创作者监控")
        creator_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        creator_btn.clicked.connect(self.show_creator_monitor)
        self.toolbar.addWidget(creator_btn)
        
        # 历史记录
        history_btn = QToolButton()
        history_btn.setText("历史记录")
        history_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        history_btn.clicked.connect(self.show_history)
        self.toolbar.addWidget(history_btn)
        
        # 首选项
        pref_btn = QToolButton()
        pref_btn.setText("首选项")
        pref_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        pref_btn.clicked.connect(self.show_preferences)
        self.toolbar.addWidget(pref_btn)
    
    def setup_main_ui(self):
        """设置主界面"""
        # URL输入框
        input_frame = QFrame()
        input_frame.setObjectName("InputFrame")
        input_layout = QHBoxLayout(input_frame)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴视频链接")
        self.url_input.setObjectName("UrlInput")
        
        download_btn = QPushButton("下载")
        download_btn.setObjectName("DownloadBtn")
        download_btn.clicked.connect(self.start_download)
        
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(download_btn)
        
        # 智能模式开关
        smart_mode = QCheckBox("智能模式")
        smart_mode.setObjectName("SmartMode")
        smart_mode.setChecked(True)
        
        # 下载区域
        drop_area = QLabel("拖放链接到此处开始下载")
        drop_area.setObjectName("DropArea")
        drop_area.setAlignment(Qt.AlignCenter)
        drop_area.setMinimumHeight(300)
        
        # 添加到主布局
        self.content_layout.addWidget(input_frame)
        self.content_layout.addWidget(smart_mode)
        self.content_layout.addWidget(drop_area)
    
    def setup_dialogs(self):
        """创建对话框"""
        self.creator_dialog = CreatorMonitorDialog(self)
        self.history_dialog = HistoryDialog(self)
        self.preferences_dialog = PreferencesDialog(self)
    
    def show_creator_monitor(self):
        """显示创作者监控对话框"""
        self.creator_dialog.show()
    
    def show_history(self):
        """显示历史记录对话框"""
        self.history_dialog.show()
    
    def show_preferences(self):
        """显示首选项对话框"""
        self.preferences_dialog.show()
    
    def start_download(self):
        """开始下载"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "警告", "请输入视频URL")
            return
        
        # TODO: 实现下载逻辑
        self.url_input.clear() 