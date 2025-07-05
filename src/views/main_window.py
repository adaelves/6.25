"""主窗口模块"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QStackedWidget,
    QListWidget, QListWidgetItem, QCheckBox, QComboBox, QSpinBox,
    QDialog, QScrollArea, QTabWidget, QProgressBar, QSplitter,
    QTreeWidget, QTreeWidgetItem, QMenuBar, QMenu,
    QStatusBar, QStyle, QDockWidget, QFormLayout, QFileDialog,
    QMessageBox
)
from PySide6.QtCore import Qt, QSize, Signal, Slot, QThread, QModelIndex
from PySide6.QtGui import QIcon, QFont, QColor, QPalette, QBrush, QPixmap, QImage, QAction


class DownloadTask:
    """下载任务类，用于存储和管理下载任务"""
    def __init__(self, url, title, quality="1080p", status="等待下载", progress=0):
        self.url = url
        self.title = title
        self.quality = quality
        self.status = status
        self.progress = progress
    
    def update_progress(self, progress):
        self.progress = progress
    
    def update_status(self, status):
        self.status = status

class DownloadTaskWidget(QWidget):
    """下载任务项组件"""
    remove_task = Signal(str)
    
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # 标题标签
        title_label = QLabel(self.task.title)
        title_label.setMaximumWidth(300)
        title_label.setWordWrap(True)
        
        # 质量标签
        quality_label = QLabel(f"质量: {self.task.quality}")
        quality_label.setStyleSheet("color: #666; font-size: 12px;")
        
        # 状态标签
        status_label = QLabel(f"状态: {self.task.status}")
        status_label.setStyleSheet("color: #007AFF; font-size: 12px;")
        
        # 进度条
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(self.task.progress)
        progress_bar.setFixedWidth(200)
        
        # 移除按钮
        remove_btn = QPushButton("移除")
        remove_btn.setFixedWidth(60)
        remove_btn.clicked.connect(lambda: self.remove_task.emit(self.task.url))
        
        # 添加到布局
        layout.addWidget(title_label)
        layout.addWidget(quality_label)
        layout.addWidget(status_label)
        layout.addWidget(progress_bar)
        layout.addWidget(remove_btn)
        
        self.setLayout(layout)
    
    def update_task(self, task):
        self.task = task
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QLabel):
                if "质量" in widget.text():
                    widget.setText(f"质量: {task.quality}")
                elif "状态" in widget.text():
                    widget.setText(f"状态: {task.status}")
                elif widget.text() == self.task.title:
                    widget.setText(task.title)
            elif isinstance(widget, QProgressBar):
                widget.setValue(task.progress)

class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("4K Video Downloader Plus")
        self.setMinimumSize(1000, 700)
        self.setup_ui()
        self.apply_styles()
    
    def setup_ui(self):
        """设置UI"""
        # 设置中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建选项卡部件
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setTabPosition(QTabWidget.North)
        
        # 添加各个功能页面
        self.download_manager = DownloadManager()
        self.history_manager = HistoryManager()
        self.creator_monitor = CreatorMonitor()
        self.settings_panel = SettingsPanel()
        
        self.tab_widget.addTab(self.download_manager, "下载")
        self.tab_widget.addTab(self.history_manager, "历史记录")
        self.tab_widget.addTab(self.creator_monitor, "创作者")
        self.tab_widget.addTab(self.settings_panel, "设置")
        
        # 添加到主布局
        main_layout.addWidget(self.tab_widget)
        
        # 设置状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
        # 连接信号
        self.download_manager.add_task.connect(self.on_add_task)
    
    def apply_styles(self):
        """应用样式"""
        self.setStyleSheet("""
            QMainWindow {
                background: #F8F8F8;
                font-family: -apple-system, BlinkMacSystemFont;
            }
            QTabWidget::pane {
                border: none;
                background: white;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background: #F8F8F8;
                color: #666;
                min-width: 100px;
                padding: 8px 16px;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #007AFF;
                border-bottom: 2px solid #007AFF;
            }
            QTabBar::tab:hover {
                color: #0066CC;
            }
            QStatusBar {
                background: #F8F8F8;
                color: #666;
            }
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #CCC;
                border-radius: 4px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #007AFF;
            }
            QPushButton {
                background: #007AFF;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 80px;
            }
            QPushButton:hover {
                background: #0066CC;
            }
            QPushButton:pressed {
                background: #0055AA;
            }
            QComboBox {
                padding: 8px 12px;
                border: 1px solid #CCC;
                border-radius: 4px;
                background: white;
            }
            QComboBox:hover {
                border-color: #999;
            }
            QComboBox:focus {
                border-color: #007AFF;
            }
        """)
    
    @Slot(str, str, str)
    def on_add_task(self, url: str, title: str, quality: str):
        """添加下载任务的槽函数"""
        self.status_bar.showMessage(f"开始下载: {title}")
        # 这里应该实现实际的下载逻辑

class DownloadManager(QWidget):
    """下载管理主界面"""
    add_task = Signal(str, str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks = []
        self.init_ui()
    
    def init_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        
        # 顶部输入区域
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        # URL输入框
        url_label = QLabel("视频URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴视频URL...")
        self.url_input.setMinimumWidth(400)
        
        # 质量选择
        quality_label = QLabel("质量:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["1080p", "720p", "480p", "360p", "音频"])
        
        # 下载按钮
        download_btn = QPushButton("开始下载")
        download_btn.clicked.connect(self.start_download)
        
        # 添加到输入布局
        input_layout.addWidget(url_label)
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(quality_label)
        input_layout.addWidget(self.quality_combo)
        input_layout.addWidget(download_btn)
        
        # 任务列表区域
        tasks_label = QLabel("下载任务")
        tasks_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        
        self.tasks_layout = QVBoxLayout()
        self.tasks_layout.setSpacing(5)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.tasks_container = QWidget()
        self.tasks_container.setLayout(self.tasks_layout)
        scroll_area.setWidget(self.tasks_container)
        
        # 添加到主布局
        main_layout.addLayout(input_layout)
        main_layout.addWidget(tasks_label)
        main_layout.addWidget(scroll_area)
        main_layout.addStretch()
    
    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "警告", "请输入视频URL")
            return
        
        quality = self.quality_combo.currentText()
        # 这里应该调用解析URL的函数获取视频标题
        title = "示例视频标题"  # 实际应用中应从URL解析
        
        self.add_task.emit(url, title, quality)
        self.url_input.clear()

class HistoryManager(QWidget):
    """历史记录管理界面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("下载历史记录")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin: 10px 0;")
        
        # 历史记录列表
        self.history_list = QListWidget()
        
        # 清空历史按钮
        clear_btn = QPushButton("清空历史记录")
        clear_btn.clicked.connect(self.clear_history)
        
        # 添加到布局
        layout.addWidget(title_label)
        layout.addWidget(self.history_list)
        layout.addWidget(clear_btn)
    
    def clear_history(self):
        reply = QMessageBox.question(self, "确认", "确定要清空所有历史记录吗？", 
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.history_list.clear()

class CreatorMonitor(QWidget):
    """创作者监控界面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 顶部控制区域
        control_layout = QHBoxLayout()
        
        # 添加创作者按钮
        add_btn = QPushButton("添加创作者")
        add_btn.clicked.connect(self.add_creator_dialog)
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        
        # 添加到控制布局
        control_layout.addWidget(add_btn)
        control_layout.addWidget(refresh_btn)
        control_layout.addStretch()
        
        # 创作者列表
        self.creator_tree = QTreeWidget()
        self.creator_tree.setHeaderLabels(["创作者", "平台", "最新视频", "更新时间"])
        
        # 添加到布局
        layout.addLayout(control_layout)
        layout.addWidget(self.creator_tree)
    
    def add_creator_dialog(self):
        QMessageBox.information(self, "提示", "添加创作者功能将在后续版本中实现")

class SettingsPanel(QWidget):
    """设置面板"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 设置表单
        form_layout = QFormLayout()
        
        # 下载目录
        self.download_dir_input = QLineEdit()
        self.download_dir_input.setText("./downloads")
        self.download_dir_input.setReadOnly(True)
        
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.download_dir_input)
        
        change_dir_btn = QPushButton("更改")
        change_dir_btn.clicked.connect(self.change_download_dir)
        dir_layout.addWidget(change_dir_btn)
        
        form_layout.addRow("下载目录:", dir_layout)
        
        # 代理设置
        self.proxy_check = QCheckBox("使用代理")
        self.proxy_input = QLineEdit()
        self.proxy_input.setText("127.0.0.1:7890")
        self.proxy_input.setEnabled(False)
        self.proxy_check.toggled.connect(self.proxy_input.setEnabled)
        
        form_layout.addRow("代理设置:", self.proxy_check)
        form_layout.addRow("", self.proxy_input)
        
        # 添加到主布局
        layout.addLayout(form_layout)
        layout.addStretch()
    
    def change_download_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择下载目录", 
            self.download_dir_input.text(),
            QFileDialog.ShowDirsOnly
        )
        if dir_path:
            self.download_dir_input.setText(dir_path) 