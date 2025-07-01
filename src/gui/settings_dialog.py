"""设置对话框模块。

提供应用程序设置界面。
支持基本设置、主题切换、语言设置和网络配置。
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QCheckBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QGroupBox,
    QDialogButtonBox,
    QFileDialog,
    QTabWidget,
    QWidget
)
from PySide6.QtCore import Qt, Signal, QThread

from src.core.settings import Settings

logger = logging.getLogger(__name__)

class ProxyTestThread(QThread):
    """代理测试线程。
    
    用于在后台测试代理连接。
    
    Signals:
        status_changed: 状态变更信号
        test_finished: 测试完成信号
    """
    
    status_changed = Signal(str)  # 状态文本
    test_finished = Signal(bool)  # 测试结果
    
    def __init__(self, proxy_url: str, timeout: int):
        """初始化代理测试线程。
        
        Args:
            proxy_url: 代理地址
            timeout: 超时时间(秒)
        """
        super().__init__()
        self.proxy_url = proxy_url
        self.timeout = timeout
        
    def run(self):
        """运行测试。"""
        import requests
        
        try:
            self.status_changed.emit("正在测试...")
            
            # 解析代理地址
            if "://" not in self.proxy_url:
                self.proxy_url = f"http://{self.proxy_url}"
                
            proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url
            }
            
            # 测试连接 (使用百度作为测试网站)
            response = requests.get(
                "https://www.baidu.com",
                proxies=proxies,
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
            )
            
            if response.status_code == 200:
                self.status_changed.emit("代理可用")
                self.test_finished.emit(True)
            else:
                self.status_changed.emit(f"代理响应异常: {response.status_code}")
                self.test_finished.emit(False)
                
        except requests.exceptions.ProxyError as e:
            self.status_changed.emit("代理连接失败")
            logger.error(f"代理测试失败: {e}")
            self.test_finished.emit(False)
            
        except requests.exceptions.SSLError as e:
            self.status_changed.emit("SSL证书验证失败")
            logger.error(f"代理测试失败: {e}")
            self.test_finished.emit(False)
            
        except requests.exceptions.ConnectionError as e:
            self.status_changed.emit("网络连接失败")
            logger.error(f"代理测试失败: {e}")
            self.test_finished.emit(False)
            
        except requests.exceptions.Timeout as e:
            self.status_changed.emit("连接超时")
            logger.error(f"代理测试失败: {e}")
            self.test_finished.emit(False)
            
        except Exception as e:
            self.status_changed.emit("测试失败")
            logger.error(f"代理测试失败: {e}")
            self.test_finished.emit(False)

class SettingsDialog(QDialog):
    """设置对话框。
    
    用于配置应用程序的各项设置。
    包括基本设置、主题、语言和网络等选项。
    
    Signals:
        settings_changed: 当设置发生改变时发出
        theme_changed: 当主题改变时发出
        language_changed: 当语言改变时发出
    """
    
    settings_changed = Signal(dict)
    theme_changed = Signal(str)
    language_changed = Signal(str)
    
    def __init__(self, settings: Settings, parent=None):
        """初始化设置对话框。
        
        Args:
            settings: 设置管理器实例
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.settings = settings
        self._setup_ui()
        self._load_settings()
        
        # 创建保存线程
        self.save_thread = None
        
    def _setup_ui(self):
        """设置用户界面。"""
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        
        # 创建主布局
        layout = QVBoxLayout(self)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 基本设置选项卡
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        
        # 下载目录设置
        dir_group = QGroupBox("下载设置")
        dir_layout = QFormLayout()
        
        save_layout = QHBoxLayout()
        self.save_path = QLineEdit()
        self.save_path.setReadOnly(True)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_directory)
        save_layout.addWidget(self.save_path)
        save_layout.addWidget(browse_btn)
        dir_layout.addRow("默认下载目录:", save_layout)
        
        self.overwrite_check = QCheckBox("允许覆盖已存在的文件")
        dir_layout.addRow("文件覆盖:", self.overwrite_check)
        
        dir_group.setLayout(dir_layout)
        basic_layout.addWidget(dir_group)
        
        # 外观设置组
        appearance_group = QGroupBox("外观")
        appearance_layout = QFormLayout()
        
        # 主题选择
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["明亮", "暗黑"])
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        appearance_layout.addRow("主题:", self.theme_combo)
        
        # 语言选择
        self.language_combo = QComboBox()
        self.language_combo.addItems(["中文", "English"])
        self.language_combo.currentTextChanged.connect(self._on_language_changed)
        appearance_layout.addRow("语言:", self.language_combo)
        
        appearance_group.setLayout(appearance_layout)
        basic_layout.addWidget(appearance_group)
        
        tab_widget.addTab(basic_tab, "基本设置")
        
        # 网络设置选项卡
        network_tab = QWidget()
        network_layout = QVBoxLayout(network_tab)
        
        # 代理设置
        proxy_group = QGroupBox("代理设置")
        proxy_layout = QFormLayout()
        
        self.proxy_check = QCheckBox("使用代理")
        self.proxy_check.toggled.connect(self._on_proxy_toggled)
        proxy_layout.addRow("启用代理:", self.proxy_check)
        
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("http://127.0.0.1:7890")
        proxy_layout.addRow("代理地址:", self.proxy_edit)
        
        # 添加代理测试按钮和状态标签
        proxy_test_layout = QHBoxLayout()
        self.proxy_test_btn = QPushButton("测试代理")
        self.proxy_test_btn.clicked.connect(self._test_proxy)
        self.proxy_test_status = QLabel()
        proxy_test_layout.addWidget(self.proxy_test_btn)
        proxy_test_layout.addWidget(self.proxy_test_status)
        proxy_test_layout.addStretch()
        proxy_layout.addRow("代理测试:", proxy_test_layout)
        
        # 超时设置
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 300)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" 秒")
        proxy_layout.addRow("请求超时:", self.timeout_spin)
        
        # 重试设置
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(3)
        proxy_layout.addRow("重试次数:", self.retry_spin)
        
        proxy_group.setLayout(proxy_layout)
        network_layout.addWidget(proxy_group)
        
        tab_widget.addTab(network_tab, "网络设置")
        
        layout.addWidget(tab_widget)
        
        # 确定取消按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def _load_settings(self):
        """加载当前设置。"""
        # 基本设置
        self.save_path.setText(
            self.settings.get("download.save_dir")
        )
        self.overwrite_check.setChecked(
            self.settings.get("download.overwrite", False)
        )
        
        # 外观设置
        theme = "暗黑" if self.settings.get("ui.theme") == "dark" else "明亮"
        self.theme_combo.setCurrentText(theme)
        
        language = (
            "English"
            if self.settings.get("ui.language") == "en_US"
            else "中文"
        )
        self.language_combo.setCurrentText(language)
        
        # 网络设置
        self.proxy_check.setChecked(
            self.settings.get("proxy.enabled", False)
        )
        self.proxy_edit.setText(
            f"{self.settings.get('proxy.type', 'http')}://"
            f"{self.settings.get('proxy.host', '127.0.0.1')}:"
            f"{self.settings.get('proxy.port', 7890)}"
        )
        self.proxy_edit.setEnabled(self.proxy_check.isChecked())
        
        self.timeout_spin.setValue(
            self.settings.get("download.timeout", 30)
        )
        self.retry_spin.setValue(
            self.settings.get("download.max_retries", 3)
        )
        
    def _browse_directory(self):
        """选择下载目录。"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择下载目录",
            self.save_path.text() or str(Path.home()),
            QFileDialog.ShowDirsOnly
        )
        if directory:
            self.save_path.setText(directory)
            
    def _on_theme_changed(self, theme: str):
        """主题改变处理。
        
        Args:
            theme: 主题名称
        """
        self.theme_changed.emit(
            "dark" if theme == "暗黑" else "light"
        )
        
    def _on_language_changed(self, language: str):
        """语言改变处理。
        
        Args:
            language: 语言名称
        """
        self.language_changed.emit(
            "en_US" if language == "English" else "zh_CN"
        )
        
    def _on_proxy_toggled(self, enabled: bool):
        """代理开关处理。
        
        Args:
            enabled: 是否启用代理
        """
        self.proxy_edit.setEnabled(enabled)
        
    def _test_proxy(self):
        """测试代理连接。"""
        # 获取代理设置
        proxy_enabled = self.proxy_check.isChecked()
        if not proxy_enabled:
            self.proxy_test_status.setText("请先启用代理")
            return
            
        proxy_url = self.proxy_edit.text().strip()
        if not proxy_url:
            self.proxy_test_status.setText("请输入代理地址")
            return
            
        # 禁用按钮
        self.proxy_test_btn.setEnabled(False)
        
        # 创建并启动测试线程
        self.test_thread = ProxyTestThread(
            proxy_url=proxy_url,
            timeout=self.timeout_spin.value()
        )
        self.test_thread.status_changed.connect(self.proxy_test_status.setText)
        self.test_thread.test_finished.connect(self._on_proxy_test_finished)
        self.test_thread.start()
        
    def _on_proxy_test_finished(self, success: bool):
        """处理代理测试完成。
        
        Args:
            success: 测试是否成功
        """
        # 启用按钮
        self.proxy_test_btn.setEnabled(True)
        
        # 设置按钮样式
        if success:
            self.proxy_test_status.setStyleSheet("color: green;")
        else:
            self.proxy_test_status.setStyleSheet("color: red;")
        
    def get_settings(self) -> Dict[str, Any]:
        """获取设置。
        
        Returns:
            Dict[str, Any]: 设置字典
        """
        # 解析代理地址
        proxy_url = self.proxy_edit.text().strip()
        proxy_type = "http"
        proxy_host = "127.0.0.1"
        proxy_port = 7890
        
        if proxy_url:
            try:
                parts = proxy_url.split("://")
                if len(parts) > 1:
                    proxy_type = parts[0]
                    addr = parts[1]
                else:
                    addr = parts[0]
                    
                host_port = addr.split(":")
                proxy_host = host_port[0]
                if len(host_port) > 1:
                    proxy_port = int(host_port[1])
            except Exception as e:
                logger.warning(f"解析代理地址失败: {e}")
        
        return {
            # 下载设置
            "download.save_dir": self.save_path.text(),
            "download.overwrite": self.overwrite_check.isChecked(),
            "download.timeout": self.timeout_spin.value(),
            "download.max_retries": self.retry_spin.value(),
            "download.max_concurrent": 3,  # 添加并发下载数
            "download.chunk_size": 1024 * 1024,  # 1MB
            "download.buffer_size": 1024 * 1024 * 10,  # 10MB
            
            # 界面设置
            "ui.theme": "dark" if self.theme_combo.currentText() == "暗黑" else "light",
            "ui.language": "en_US" if self.language_combo.currentText() == "English" else "zh_CN",
            "ui.show_tray": True,
            "ui.minimize_to_tray": True,
            
            # 代理设置
            "proxy.enabled": self.proxy_check.isChecked(),
            "proxy.type": proxy_type,
            "proxy.host": proxy_host,
            "proxy.port": proxy_port
        }
        
    def accept(self):
        """确定按钮处理。"""
        try:
            # 获取设置
            settings = self.get_settings()
            
            # 禁用按钮，防止重复点击
            self.findChild(QDialogButtonBox).setEnabled(False)
            
            # 创建并启动保存线程
            self.save_thread = SaveSettingsThread(self.settings, settings)
            self.save_thread.finished.connect(self._on_save_finished)
            self.save_thread.error.connect(self._on_save_error)
            self.save_thread.start()
            
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            self.findChild(QDialogButtonBox).setEnabled(True)
            
    def _on_save_finished(self):
        """设置保存完成处理。"""
        try:
            # 发出信号
            if self.save_thread:
                self.settings_changed.emit(self.save_thread.settings)
            
            # 清理线程
            self.save_thread = None
            
            # 关闭对话框
            super().accept()
            
        except Exception as e:
            logger.error(f"保存设置完成处理失败: {e}")
            self.findChild(QDialogButtonBox).setEnabled(True)
            
    def _on_save_error(self, error_msg: str):
        """设置保存错误处理。
        
        Args:
            error_msg: 错误信息
        """
        # 显示错误消息
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "错误", f"保存设置失败: {error_msg}")
        
        # 启用按钮
        self.findChild(QDialogButtonBox).setEnabled(True)
        
        # 清理线程
        self.save_thread = None

class SaveSettingsThread(QThread):
    """设置保存线程。
    
    用于异步保存设置，避免界面卡死。
    
    Signals:
        error: 保存出错信号
    """
    
    error = Signal(str)
    
    def __init__(self, settings_manager: Settings, settings: Dict[str, Any]):
        """初始化保存线程。
        
        Args:
            settings_manager: 设置管理器
            settings: 要保存的设置
        """
        super().__init__()
        self.settings_manager = settings_manager
        self.settings = settings
        
    def run(self):
        """运行线程。"""
        try:
            # 保存设置
            for key, value in self.settings.items():
                self.settings_manager.set(key, value)
                
            # 保存到文件
            self.settings_manager.save()
                
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            self.error.emit(str(e))
            
    @classmethod
    def show_settings(
        cls,
        settings: Settings,
        parent=None
    ) -> Optional[Dict[str, Any]]:
        """显示设置对话框。
        
        Args:
            settings: 设置管理器实例
            parent: 父窗口
            
        Returns:
            Optional[Dict[str, Any]]: 如果用户点击确定则返回设置字典，否则返回 None
        """
        dialog = cls(settings, parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_settings()
        return None 