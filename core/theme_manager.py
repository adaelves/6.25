"""主题管理模块"""

import os
import logging
from typing import Optional
from PySide6.QtCore import QObject, Signal, QSettings
from PySide6.QtWidgets import QApplication

class ThemeManager(QObject):
    """主题管理器"""
    theme_changed = Signal(str)  # 主题改变信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("ThemeManager")
        self.settings = QSettings("YourCompany", "VideoDownloader")
        
        # 主题文件路径
        self.style_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "resources",
            "styles"
        )
        
        # 当前主题
        self._current_theme = self.settings.value("theme", "light")
        
        # 加载基础样式
        self._base_style = self._load_style_file("base.qss")
        
        # 加载当前主题
        self.apply_theme(self._current_theme)
    
    def _load_style_file(self, filename: str) -> str:
        """加载样式文件"""
        try:
            style_path = os.path.join(self.style_dir, filename)
            if os.path.exists(style_path):
                with open(style_path, "r", encoding="utf-8") as f:
                    return f.read()
            else:
                self.logger.warning(f"Style file not found: {filename}")
                return ""
        except Exception as e:
            self.logger.error(f"Error loading style file {filename}: {e}")
            return ""
    
    def apply_theme(self, theme_name: str) -> bool:
        """应用主题"""
        if theme_name not in ["light", "dark"]:
            self.logger.error(f"Invalid theme name: {theme_name}")
            return False
        
        try:
            # 加载主题样式
            theme_style = self._load_style_file(f"{theme_name}.qss")
            if not theme_style:
                return False
            
            # 合并基础样式和主题样式
            combined_style = f"{self._base_style}\n{theme_style}"
            
            # 应用样式
            QApplication.instance().setStyleSheet(combined_style)
            
            # 保存设置
            self._current_theme = theme_name
            self.settings.setValue("theme", theme_name)
            
            # 发送主题改变信号
            self.theme_changed.emit(theme_name)
            
            self.logger.info(f"Theme applied: {theme_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error applying theme {theme_name}: {e}")
            return False
    
    def toggle_theme(self) -> str:
        """切换主题"""
        new_theme = "dark" if self._current_theme == "light" else "light"
        self.apply_theme(new_theme)
        return new_theme
    
    @property
    def current_theme(self) -> str:
        """获取当前主题"""
        return self._current_theme
    
    def is_dark_mode(self) -> bool:
        """是否为暗色主题"""
        return self._current_theme == "dark" 