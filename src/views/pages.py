"""页面组件模块"""

from typing import Optional, Dict, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QProgressBar,
    QListWidget, QListWidgetItem, QComboBox,
    QSpinBox, QCheckBox, QFileDialog, QFrame,
    QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

class DownloadPage(QWidget):
    """下载页面"""
    
    # 信号定义
    download_requested = Signal(str, str, str)  # URL, 格式, 质量
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 顶部控制栏
        control_bar = QWidget()
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入视频URL或拖放文件")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setMinimumWidth(400)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "WebM", "MP3"])
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "最高质量", "1080p", "720p", "480p"
        ])
        
        self.download_btn = QPushButton("下载")
        self.download_btn.clicked.connect(self._on_download_clicked)
        
        control_layout.addWidget(self.url_input)
        control_layout.addWidget(self.format_combo)
        control_layout.addWidget(self.quality_combo)
        control_layout.addWidget(self.download_btn)
        
        # 下载列表
        list_frame = QFrame()
        list_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
            }
        """)
        
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(1, 1, 1, 1)
        
        self.download_list = QListWidget()
        self.download_list.setStyleSheet("""
            QListWidget {
                border: none;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #E0E0E0;
            }
        """)
        
        list_layout.addWidget(self.download_list)
        
        # 底部状态栏
        status_bar = QWidget()
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        self.speed_label = QLabel("速度: 0 KB/s")
        status_layout.addWidget(self.speed_label)
        status_layout.addStretch()
        
        # 组合布局
        layout.addWidget(control_bar)
        layout.addWidget(list_frame)
        layout.addWidget(status_bar)
    
    def _on_download_clicked(self):
        """下载按钮点击处理"""
        url = self.url_input.text().strip()
        if not url:
            return
            
        self.download_requested.emit(
            url,
            self.format_combo.currentText(),
            self.quality_combo.currentText()
        )
    
    def add_download_task(self, title: str) -> tuple[QProgressBar, QLabel]:
        """添加下载任务"""
        item = QListWidgetItem()
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 任务信息
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(f"视频: {title[:50]}..."))
        info_layout.addStretch()
        
        # 进度条和状态
        progress = QProgressBar()
        progress.setFixedHeight(6)
        progress.setTextVisible(False)
        
        status = QLabel("准备下载...")
        status.setStyleSheet("color: #666666;")
        
        layout.addLayout(info_layout)
        layout.addWidget(progress)
        layout.addWidget(status)
        
        item.setSizeHint(widget.sizeHint())
        self.download_list.addItem(item)
        self.download_list.setItemWidget(item, widget)
        
        return progress, status
    
    def update_speed(self, speed: int, remaining: int):
        """更新下载速度"""
        self.speed_label.setText(
            f"速度: {speed} KB/s | 剩余时间: {remaining}秒"
        )

class HistoryPage(QWidget):
    """历史记录页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 工具栏
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索下载记录...")
        self.search_input.setClearButtonEnabled(True)
        
        self.clear_btn = QPushButton("清空历史")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                color: #FC615D;
                border: 1px solid #FC615D;
            }
            QPushButton:hover {
                background: #FC615D;
                color: white;
            }
        """)
        
        toolbar_layout.addWidget(self.search_input)
        toolbar_layout.addWidget(self.clear_btn)
        
        # 历史记录列表
        list_frame = QFrame()
        list_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
            }
        """)
        
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(1, 1, 1, 1)
        
        self.history_list = QListWidget()
        self.history_list.setStyleSheet("""
            QListWidget {
                border: none;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #E0E0E0;
            }
        """)
        
        list_layout.addWidget(self.history_list)
        
        # 组合布局
        layout.addWidget(toolbar)
        layout.addWidget(list_frame)
    
    def add_history_item(self, data: Dict):
        """添加历史记录项
        
        Args:
            data: 下载记录数据
        """
        item = QListWidgetItem()
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 标题和时间
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel(data["title"]))
        title_layout.addStretch()
        title_layout.addWidget(QLabel(data["download_date"]))
        
        # 格式和大小
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(f"格式: {data['format']}"))
        info_layout.addWidget(QLabel(f"质量: {data['quality']}"))
        info_layout.addWidget(
            QLabel(f"大小: {data['file_size'] / 1024 / 1024:.1f}MB")
        )
        info_layout.addStretch()
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        open_btn = QPushButton("打开文件")
        open_btn.setIcon(QIcon("resources/icons/open.png"))
        
        delete_btn = QPushButton("删除")
        delete_btn.setIcon(QIcon("resources/icons/delete.png"))
        
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(delete_btn)
        
        layout.addLayout(title_layout)
        layout.addLayout(info_layout)
        layout.addLayout(btn_layout)
        
        item.setSizeHint(widget.sizeHint())
        self.history_list.addItem(item)
        self.history_list.setItemWidget(item, widget)

class CreatorPage(QWidget):
    """创作者监控页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 工具栏
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.add_btn = QPushButton("添加创作者")
        self.add_btn.setIcon(QIcon("resources/icons/add.png"))
        
        toolbar_layout.addWidget(self.add_btn)
        toolbar_layout.addStretch()
        
        # 创作者列表
        list_frame = QFrame()
        list_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
            }
        """)
        
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(1, 1, 1, 1)
        
        self.creator_list = QListWidget()
        self.creator_list.setStyleSheet("""
            QListWidget {
                border: none;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #E0E0E0;
            }
        """)
        
        list_layout.addWidget(self.creator_list)
        
        # 组合布局
        layout.addWidget(toolbar)
        layout.addWidget(list_frame)
    
    def add_creator_item(self, data: Dict):
        """添加创作者项
        
        Args:
            data: 创作者数据
        """
        item = QListWidgetItem()
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 创作者信息
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(data["name"]))
        info_layout.addWidget(QLabel(f"平台: {data['platform']}"))
        info_layout.addStretch()
        
        # 监控设置
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("自动下载:"))
        settings_layout.addWidget(QCheckBox())
        settings_layout.addWidget(QLabel("通知提醒:"))
        settings_layout.addWidget(QCheckBox())
        settings_layout.addStretch()
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        update_btn = QPushButton("更新")
        update_btn.setIcon(QIcon("resources/icons/refresh.png"))
        
        delete_btn = QPushButton("删除")
        delete_btn.setIcon(QIcon("resources/icons/delete.png"))
        
        btn_layout.addWidget(update_btn)
        btn_layout.addWidget(delete_btn)
        
        layout.addLayout(info_layout)
        layout.addLayout(settings_layout)
        layout.addLayout(btn_layout)
        
        item.setSizeHint(widget.sizeHint())
        self.creator_list.addItem(item)
        self.creator_list.setItemWidget(item, widget)

class SettingsPage(QWidget):
    """设置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 下载设置
        download_group = QFrame()
        download_group.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
            }
        """)
        
        download_layout = QVBoxLayout(download_group)
        download_layout.setContentsMargins(16, 16, 16, 16)
        download_layout.setSpacing(12)
        
        download_layout.addWidget(QLabel("下载设置"))
        
        # 下载路径
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit("downloads")
        browse_btn = QPushButton("浏览...")
        path_layout.addWidget(QLabel("下载路径:"))
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        
        # 线程数
        thread_layout = QHBoxLayout()
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 8)
        self.thread_spin.setValue(4)
        thread_layout.addWidget(QLabel("最大线程数:"))
        thread_layout.addWidget(self.thread_spin)
        thread_layout.addStretch()
        
        download_layout.addLayout(path_layout)
        download_layout.addLayout(thread_layout)
        
        # 代理设置
        proxy_group = QFrame()
        proxy_group.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
            }
        """)
        
        proxy_layout = QVBoxLayout(proxy_group)
        proxy_layout.setContentsMargins(16, 16, 16, 16)
        proxy_layout.setSpacing(12)
        
        proxy_layout.addWidget(QLabel("代理设置"))
        
        self.proxy_check = QCheckBox("使用代理")
        self.proxy_input = QLineEdit("127.0.0.1:7890")
        self.proxy_input.setEnabled(False)
        self.proxy_check.toggled.connect(self.proxy_input.setEnabled)
        
        proxy_layout.addWidget(self.proxy_check)
        proxy_layout.addWidget(self.proxy_input)
        
        # 组合布局
        layout.addWidget(download_group)
        layout.addWidget(proxy_group)
        layout.addStretch() 