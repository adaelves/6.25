from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QFileDialog,
    QMessageBox
)
from PySide6.QtCore import Qt
import logging

logger = logging.getLogger(__name__)

class SettingsPage(QDialog):
    """设置页面。"""
    
    def __init__(self, settings, parent=None):
        """初始化设置页面。
        
        Args:
            settings: 配置信息
            parent: 父窗口
        """
        super().__init__(parent)
        self.settings = settings
        self._setup_ui()
        self._load_settings()
        
    def _setup_ui(self):
        """创建界面。"""
        self.setWindowTitle("设置")
        self.setMinimumWidth(600)
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                font-size: 14px;
            }
            QLineEdit, QSpinBox, QComboBox {
                padding: 5px;
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                background-color: #1890ff;
                color: white;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
            QPushButton:pressed {
                background-color: #096dd9;
            }
            QPushButton[flat=true] {
                background-color: transparent;
                color: #1890ff;
            }
            QPushButton[flat=true]:hover {
                color: #40a9ff;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 下载设置
        download_group = QLabel("下载设置")
        download_group.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #333;
            }
        """)
        
        # 保存路径
        save_path_layout = QHBoxLayout()
        save_path_label = QLabel("保存路径")
        self.save_path_edit = QLineEdit()
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._browse_save_path)
        
        save_path_layout.addWidget(save_path_label)
        save_path_layout.addWidget(self.save_path_edit)
        save_path_layout.addWidget(browse_btn)
        
        # 最大并发数
        concurrent_layout = QHBoxLayout()
        concurrent_label = QLabel("最大并发数")
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setMinimum(1)
        self.concurrent_spin.setMaximum(10)
        
        concurrent_layout.addWidget(concurrent_label)
        concurrent_layout.addWidget(self.concurrent_spin)
        concurrent_layout.addStretch()
        
        # 速度限制
        speed_layout = QHBoxLayout()
        speed_label = QLabel("速度限制")
        self.speed_spin = QSpinBox()
        self.speed_spin.setMinimum(0)
        self.speed_spin.setMaximum(100000)
        self.speed_spin.setSuffix(" KB/s")
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.speed_spin)
        speed_layout.addStretch()
        
        # 代理设置
        proxy_group = QLabel("代理设置")
        proxy_group.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #333;
            }
        """)
        
        # 启用代理
        proxy_enable_layout = QHBoxLayout()
        self.proxy_enable = QCheckBox("启用代理")
        self.proxy_type = QComboBox()
        self.proxy_type.addItems(["HTTP", "SOCKS"])
        
        proxy_enable_layout.addWidget(self.proxy_enable)
        proxy_enable_layout.addWidget(self.proxy_type)
        proxy_enable_layout.addStretch()
        
        # 代理地址
        proxy_layout = QHBoxLayout()
        proxy_label = QLabel("代理地址")
        self.proxy_host = QLineEdit()
        self.proxy_host.setPlaceholderText("127.0.0.1")
        
        proxy_port_label = QLabel("端口")
        self.proxy_port = QSpinBox()
        self.proxy_port.setMinimum(1)
        self.proxy_port.setMaximum(65535)
        self.proxy_port.setValue(7890)
        
        proxy_layout.addWidget(proxy_label)
        proxy_layout.addWidget(self.proxy_host)
        proxy_layout.addWidget(proxy_port_label)
        proxy_layout.addWidget(self.proxy_port)
        
        # 按钮
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.setFlat(True)
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save_settings)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        # 添加到主布局
        layout.addWidget(download_group)
        layout.addLayout(save_path_layout)
        layout.addLayout(concurrent_layout)
        layout.addLayout(speed_layout)
        layout.addWidget(proxy_group)
        layout.addLayout(proxy_enable_layout)
        layout.addLayout(proxy_layout)
        layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def _load_settings(self):
        """加载设置。"""
        self.save_path_edit.setText(self.settings.get('download.save_path', ''))
        self.concurrent_spin.setValue(self.settings.get('download.max_concurrent', 3))
        self.speed_spin.setValue(self.settings.get('download.speed_limit', 0))
        
        proxy_enabled = self.settings.get('proxy.enabled', False)
        self.proxy_enable.setChecked(proxy_enabled)
        
        proxy_type = self.settings.get('proxy.type', 'HTTP')
        self.proxy_type.setCurrentText(proxy_type)
        
        proxy_host = self.settings.get('proxy.host', '127.0.0.1')
        self.proxy_host.setText(proxy_host)
        
        proxy_port = self.settings.get('proxy.port', 7890)
        self.proxy_port.setValue(proxy_port)
        
    def _save_settings(self):
        """保存设置。"""
        try:
            self.settings.set('download.save_path', self.save_path_edit.text())
            self.settings.set('download.max_concurrent', self.concurrent_spin.value())
            self.settings.set('download.speed_limit', self.speed_spin.value())
            
            self.settings.set('proxy.enabled', self.proxy_enable.isChecked())
            self.settings.set('proxy.type', self.proxy_type.currentText())
            self.settings.set('proxy.host', self.proxy_host.text())
            self.settings.set('proxy.port', self.proxy_port.value())
            
            self.accept()
            
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存设置失败: {e}")
            
    def _browse_save_path(self):
        """选择保存路径。"""
        path = QFileDialog.getExistingDirectory(
            self,
            "选择保存路径",
            self.save_path_edit.text()
        )
        if path:
            self.save_path_edit.setText(path) 