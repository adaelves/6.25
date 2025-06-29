"""设置对话框模块。

提供下载器配置界面。
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QTabWidget,
    QWidget,
    QFormLayout,
    QComboBox,
    QFileDialog,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal

class SettingsDialog(QDialog):
    """设置对话框。
    
    提供以下配置项：
    1. 下载设置
        - 保存目录
        - 最大并发数
        - 默认超时时间
        - 最大重试次数
        - 块大小
        - 缓冲区大小
        
    2. 网络设置
        - 代理设置
        - 请求头
        - Cookie
        
    3. 缓存设置
        - 缓存目录
        - 最大内存缓存
        - 最大文件缓存
        - 默认过期时间
        
    4. 安全设置
        - 签名密钥
        
    Signals:
        settings_changed: 设置变更信号
    """
    
    settings_changed = Signal(dict)
    
    def __init__(
        self,
        settings: Dict[str, Any],
        parent: Optional[QWidget] = None
    ):
        """初始化设置对话框。
        
        Args:
            settings: 当前设置
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.settings = settings.copy()
        
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        
        # 创建界面
        self._create_ui()
        
        # 加载设置
        self._load_settings()
        
    def _create_ui(self):
        """创建界面。"""
        layout = QVBoxLayout()
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 下载设置
        download_tab = QWidget()
        download_layout = QFormLayout()
        
        # 保存目录
        self.save_dir = QLineEdit()
        browse_button = QPushButton("浏览")
        browse_button.clicked.connect(self._browse_save_dir)
        save_dir_layout = QHBoxLayout()
        save_dir_layout.addWidget(self.save_dir)
        save_dir_layout.addWidget(browse_button)
        download_layout.addRow("保存目录:", save_dir_layout)
        
        # 最大并发数
        self.max_concurrent = QSpinBox()
        self.max_concurrent.setRange(1, 10)
        download_layout.addRow("最大并发数:", self.max_concurrent)
        
        # 默认超时时间
        self.default_timeout = QSpinBox()
        self.default_timeout.setRange(10, 300)
        self.default_timeout.setSuffix(" 秒")
        download_layout.addRow("默认超时:", self.default_timeout)
        
        # 最大重试次数
        self.max_retries = QSpinBox()
        self.max_retries.setRange(0, 10)
        download_layout.addRow("最大重试:", self.max_retries)
        
        # 块大小
        self.chunk_size = QSpinBox()
        self.chunk_size.setRange(1024, 1024*1024)
        self.chunk_size.setSingleStep(1024)
        self.chunk_size.setSuffix(" bytes")
        download_layout.addRow("块大小:", self.chunk_size)
        
        # 缓冲区大小
        self.buffer_size = QSpinBox()
        self.buffer_size.setRange(1024*1024, 10*1024*1024)
        self.buffer_size.setSingleStep(1024*1024)
        self.buffer_size.setSuffix(" bytes")
        download_layout.addRow("缓冲区大小:", self.buffer_size)
        
        download_tab.setLayout(download_layout)
        tab_widget.addTab(download_tab, "下载")
        
        # 网络设置
        network_tab = QWidget()
        network_layout = QFormLayout()
        
        # 代理设置
        self.proxy = QLineEdit()
        self.proxy.setPlaceholderText("http://user:pass@host:port")
        network_layout.addRow("代理地址:", self.proxy)
        
        # 请求头
        self.headers = QLineEdit()
        self.headers.setPlaceholderText('{"User-Agent": "..."}')
        network_layout.addRow("请求头:", self.headers)
        
        # Cookie
        self.cookies = QLineEdit()
        self.cookies.setPlaceholderText('{"name": "value"}')
        network_layout.addRow("Cookie:", self.cookies)
        
        network_tab.setLayout(network_layout)
        tab_widget.addTab(network_tab, "网络")
        
        # 缓存设置
        cache_tab = QWidget()
        cache_layout = QFormLayout()
        
        # 缓存目录
        self.cache_dir = QLineEdit()
        browse_cache_button = QPushButton("浏览")
        browse_cache_button.clicked.connect(self._browse_cache_dir)
        cache_dir_layout = QHBoxLayout()
        cache_dir_layout.addWidget(self.cache_dir)
        cache_dir_layout.addWidget(browse_cache_button)
        cache_layout.addRow("缓存目录:", cache_dir_layout)
        
        # 最大内存缓存
        self.max_memory_cache = QSpinBox()
        self.max_memory_cache.setRange(10, 1000)
        self.max_memory_cache.setSuffix(" MB")
        cache_layout.addRow("最大内存缓存:", self.max_memory_cache)
        
        # 最大文件缓存
        self.max_file_cache = QSpinBox()
        self.max_file_cache.setRange(100, 10000)
        self.max_file_cache.setSuffix(" MB")
        cache_layout.addRow("最大文件缓存:", self.max_file_cache)
        
        # 默认过期时间
        self.default_ttl = QSpinBox()
        self.default_ttl.setRange(60, 86400)
        self.default_ttl.setSuffix(" 秒")
        cache_layout.addRow("默认过期时间:", self.default_ttl)
        
        cache_tab.setLayout(cache_layout)
        tab_widget.addTab(cache_tab, "缓存")
        
        # 安全设置
        security_tab = QWidget()
        security_layout = QFormLayout()
        
        # 签名密钥
        self.secret_key = QLineEdit()
        self.secret_key.setEchoMode(QLineEdit.Password)
        security_layout.addRow("签名密钥:", self.secret_key)
        
        security_tab.setLayout(security_layout)
        tab_widget.addTab(security_tab, "安全")
        
        layout.addWidget(tab_widget)
        
        # 按钮
        button_layout = QHBoxLayout()
        save_button = QPushButton("保存")
        save_button.clicked.connect(self._save_settings)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def _load_settings(self):
        """加载设置。"""
        # 下载设置
        self.save_dir.setText(str(self.settings.get('save_dir', '')))
        self.max_concurrent.setValue(self.settings.get('max_concurrent', 3))
        self.default_timeout.setValue(self.settings.get('default_timeout', 30))
        self.max_retries.setValue(self.settings.get('max_retries', 3))
        self.chunk_size.setValue(self.settings.get('chunk_size', 8192))
        self.buffer_size.setValue(self.settings.get('buffer_size', 1024*1024))
        
        # 网络设置
        self.proxy.setText(self.settings.get('proxy', ''))
        self.headers.setText(
            json.dumps(self.settings.get('headers', {}))
            if self.settings.get('headers') else ''
        )
        self.cookies.setText(
            json.dumps(self.settings.get('cookies', {}))
            if self.settings.get('cookies') else ''
        )
        
        # 缓存设置
        self.cache_dir.setText(str(self.settings.get('cache_dir', '')))
        self.max_memory_cache.setValue(
            self.settings.get('max_memory_cache', 100)
        )
        self.max_file_cache.setValue(
            self.settings.get('max_file_cache', 1000)
        )
        self.default_ttl.setValue(self.settings.get('default_ttl', 3600))
        
        # 安全设置
        self.secret_key.setText(self.settings.get('secret_key', ''))
        
    def _save_settings(self):
        """保存设置。"""
        try:
            # 验证JSON格式
            headers = (
                json.loads(self.headers.text())
                if self.headers.text() else {}
            )
            cookies = (
                json.loads(self.cookies.text())
                if self.cookies.text() else {}
            )
            
            # 更新设置
            self.settings.update({
                # 下载设置
                'save_dir': Path(self.save_dir.text()),
                'max_concurrent': self.max_concurrent.value(),
                'default_timeout': self.default_timeout.value(),
                'max_retries': self.max_retries.value(),
                'chunk_size': self.chunk_size.value(),
                'buffer_size': self.buffer_size.value(),
                
                # 网络设置
                'proxy': self.proxy.text(),
                'headers': headers,
                'cookies': cookies,
                
                # 缓存设置
                'cache_dir': (
                    Path(self.cache_dir.text())
                    if self.cache_dir.text() else None
                ),
                'max_memory_cache': self.max_memory_cache.value(),
                'max_file_cache': self.max_file_cache.value(),
                'default_ttl': self.default_ttl.value(),
                
                # 安全设置
                'secret_key': self.secret_key.text()
            })
            
            # 发送信号
            self.settings_changed.emit(self.settings)
            
            # 关闭对话框
            self.accept()
            
        except json.JSONDecodeError:
            QMessageBox.warning(
                self,
                "错误",
                "请求头或Cookie格式错误，请使用正确的JSON格式"
            )
            
    def _browse_save_dir(self):
        """浏览保存目录。"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            self.save_dir.text()
        )
        if dir_path:
            self.save_dir.setText(dir_path)
            
    def _browse_cache_dir(self):
        """浏览缓存目录。"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择缓存目录",
            self.cache_dir.text()
        )
        if dir_path:
            self.cache_dir.setText(dir_path) 