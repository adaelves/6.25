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
    QTabWidget
)
from PySide6.QtCore import Qt, Signal

from src.utils.config import ConfigManager
from src.gui.theme import ThemeManager

logger = logging.getLogger(__name__)

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
    
    def __init__(self, config: ConfigManager, theme_manager: ThemeManager, parent=None):
        """初始化设置对话框。
        
        Args:
            config: 配置管理器实例
            theme_manager: 主题管理器实例
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.config = config
        self.theme_manager = theme_manager
        self._setup_ui()
        self._load_settings()
        
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
        settings = self.config.get_settings()
        
        # 基本设置
        self.save_path.setText(settings.get("download_dir", str(Path.home() / "Downloads")))
        self.overwrite_check.setChecked(settings.get("allow_overwrite", False))
        
        # 外观设置
        theme = settings.get("theme", "明亮")
        self.theme_combo.setCurrentText(theme)
        
        language = settings.get("language", "中文")
        self.language_combo.setCurrentText(language)
        
        # 网络设置
        proxy = settings.get("proxy", {})
        self.proxy_check.setChecked(proxy.get("enabled", False))
        self.proxy_edit.setText(proxy.get("url", ""))
        self.proxy_edit.setEnabled(self.proxy_check.isChecked())
        
        self.timeout_spin.setValue(settings.get("timeout", 30))
        self.retry_spin.setValue(settings.get("max_retries", 3))
        
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
            theme: 新的主题名称
        """
        self.theme_changed.emit(theme)
            
    def _on_language_changed(self, language: str):
        """语言改变处理。
        
        Args:
            language: 新的语言名称
        """
        self.language_changed.emit(language)
            
    def _on_proxy_toggled(self, enabled: bool):
        """代理开关处理。
        
        Args:
            enabled: 是否启用代理
        """
        self.proxy_edit.setEnabled(enabled)
        
    def get_settings(self) -> Dict[str, Any]:
        """获取设置值。
        
        Returns:
            Dict[str, Any]: 设置字典
        """
        return {
            "download_dir": self.save_path.text(),
            "allow_overwrite": self.overwrite_check.isChecked(),
            "theme": self.theme_combo.currentText(),
            "language": self.language_combo.currentText(),
            "proxy": {
                "enabled": self.proxy_check.isChecked(),
                "url": self.proxy_edit.text()
            },
            "timeout": self.timeout_spin.value(),
            "max_retries": self.retry_spin.value()
        }
        
    def accept(self):
        """确认对话框。"""
        try:
            settings = self.get_settings()
            self.config.update_settings(settings)
            self.settings_changed.emit(settings)
            logger.info("设置已更新")
            super().accept()
        except Exception as e:
            logger.error(f"保存设置时出错: {str(e)}")
            
    @classmethod
    def show_settings(
        cls,
        config: ConfigManager,
        theme_manager: ThemeManager,
        parent=None
    ) -> Optional[Dict[str, Any]]:
        """显示设置对话框。
        
        Args:
            config: 配置管理器实例
            theme_manager: 主题管理器实例
            parent: 父窗口
            
        Returns:
            Optional[Dict[str, Any]]: 设置字典，如果用户取消则返回None
        """
        dialog = cls(config, theme_manager, parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_settings()
        return None 