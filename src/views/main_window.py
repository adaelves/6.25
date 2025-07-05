from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QListWidget,
    QListWidgetItem, QTabWidget, QComboBox, QSpinBox, QCheckBox,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon

class MainWindow(QMainWindow):
    """主窗口视图类"""
    
    # 信号定义
    download_requested = Signal(str, str, str)  # URL, 格式, 质量
    path_changed = Signal(str)  # 下载路径
    
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(self.tr("4K Style Video Downloader"))
        self.setWindowIcon(QIcon("resources/icons/app.png"))
        self.setGeometry(100, 100, 800, 600)
        
        self._setup_ui()
        self._setup_stylesheet()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """设置UI布局"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 顶部：URL输入 + 下载按钮
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(self.tr("粘贴视频链接（支持批量下载）"))
        self.download_btn = QPushButton(self.tr("下载"))
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.download_btn)
        
        # 格式和质量选择
        format_layout = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "WebM", "MP3"])
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            self.tr("最高质量"), "1080p", "720p", "480p"
        ])
        format_layout.addWidget(QLabel(self.tr("格式:")))
        format_layout.addWidget(self.format_combo)
        format_layout.addWidget(QLabel(self.tr("质量:")))
        format_layout.addWidget(self.quality_combo)
        
        # 全局速度显示
        self.speed_label = QLabel(self.tr("下载速度: 0 KB/s | 剩余时间: --"))
        self.speed_label.setAlignment(Qt.AlignRight)
        
        # 主Tab布局
        self.tabs = QTabWidget()
        self._setup_download_tab()
        self._setup_history_tab()
        self._setup_creator_tab()
        self._setup_settings_tab()
        
        # 添加到主布局
        layout.addLayout(url_layout)
        layout.addLayout(format_layout)
        layout.addWidget(self.speed_label)
        layout.addWidget(self.tabs)
    
    def _setup_stylesheet(self) -> None:
        """设置样式表"""
        with open("resources/styles/dark.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())
    
    def _setup_connections(self) -> None:
        """设置信号连接"""
        self.download_btn.clicked.connect(self._on_download_clicked)
        
    def _setup_download_tab(self) -> None:
        """设置下载任务标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.download_list = QListWidget()
        layout.addWidget(self.download_list)
        self.tabs.addTab(tab, self.tr("下载"))
        
    def _setup_history_tab(self) -> None:
        """设置历史记录标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)
        self.tabs.addTab(tab, self.tr("历史记录"))
        
    def _setup_creator_tab(self) -> None:
        """设置创作者监控标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.creator_list = QListWidget()
        self.add_creator_btn = QPushButton(self.tr("+ 添加创作者"))
        layout.addWidget(self.creator_list)
        layout.addWidget(self.add_creator_btn)
        self.tabs.addTab(tab, self.tr("创作者监控"))
        
    def _setup_settings_tab(self) -> None:
        """设置设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 下载路径
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit("downloads")
        browse_btn = QPushButton(self.tr("浏览..."))
        browse_btn.clicked.connect(self._on_browse_path)
        path_layout.addWidget(QLabel(self.tr("下载路径:")))
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        
        # 线程数
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 8)
        self.thread_spin.setValue(4)
        
        # 代理设置
        self.proxy_check = QCheckBox(self.tr("使用代理"))
        self.proxy_input = QLineEdit("127.0.0.1:7890")
        self.proxy_input.setEnabled(False)
        self.proxy_check.toggled.connect(self.proxy_input.setEnabled)
        
        layout.addLayout(path_layout)
        layout.addWidget(QLabel(self.tr("最大线程数:")))
        layout.addWidget(self.thread_spin)
        layout.addWidget(self.proxy_check)
        layout.addWidget(self.proxy_input)
        layout.addStretch()
        
        self.tabs.addTab(tab, self.tr("设置"))
    
    def _on_download_clicked(self) -> None:
        """下载按钮点击处理"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(
                self,
                self.tr("错误"),
                self.tr("请输入视频链接！")
            )
            return
            
        self.download_requested.emit(
            url,
            self.format_combo.currentText(),
            self.quality_combo.currentText()
        )
        
    def _on_browse_path(self) -> None:
        """浏览下载路径"""
        path = QFileDialog.getExistingDirectory(
            self,
            self.tr("选择下载目录")
        )
        if path:
            self.path_input.setText(path)
            self.path_changed.emit(path)
            
    def add_download_task(self, title: str) -> tuple[QProgressBar, QLabel]:
        """添加下载任务到列表
        
        Args:
            title: 视频标题
            
        Returns:
            tuple: (进度条, 状态标签)
        """
        item = QListWidgetItem()
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 任务信息
        layout.addWidget(QLabel(f"{self.tr('视频')}: {title[:30]}..."))
        
        progress = QProgressBar()
        status = QLabel(self.tr("准备下载..."))
        
        layout.addWidget(progress)
        layout.addWidget(status)
        
        item.setSizeHint(widget.sizeHint())
        self.download_list.addItem(item)
        self.download_list.setItemWidget(item, widget)
        
        return progress, status
        
    def update_speed(self, speed: int, remaining: int) -> None:
        """更新下载速度显示
        
        Args:
            speed: 下载速度(KB/s)
            remaining: 剩余时间(秒)
        """
        self.speed_label.setText(
            f"{self.tr('下载速度')}: {speed} KB/s | "
            f"{self.tr('剩余时间')}: {remaining}{self.tr('秒')}"
        ) 