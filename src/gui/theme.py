"""主题管理模块。

提供应用程序的主题管理功能。
支持暗色/亮色主题切换。
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from PySide6.QtCore import QSettings
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

def load_style(dark_mode: bool = False) -> str:
    """加载主题样式。
    
    Args:
        dark_mode: 是否为暗色主题
        
    Returns:
        str: 样式表内容
    """
    try:
        # 获取样式文件路径
        style_dir = Path(__file__).parent / "styles"
        style_file = style_dir / ("dark.qss" if dark_mode else "light.qss")
        
        # 如果样式目录不存在，创建它
        style_dir.mkdir(parents=True, exist_ok=True)
        
        # 如果样式文件不存在，创建默认样式
        if not style_file.exists():
            style_content = _get_default_style(dark_mode)
            with open(style_file, "w", encoding="utf-8") as f:
                f.write(style_content)
            logger.info(f"已创建默认样式文件: {style_file}")
            return style_content
            
        # 读取样式文件
        with open(style_file, "r", encoding="utf-8") as f:
            style = f.read()
        logger.info(f"已加载样式文件: {style_file}")
        return style
        
    except Exception as e:
        logger.error(f"加载样式失败: {str(e)}")
        return _get_default_style(dark_mode)

def _get_default_style(dark_mode: bool = False) -> str:
    """获取默认样式。
    
    Args:
        dark_mode: 是否为暗色主题
        
    Returns:
        str: 默认样式内容
    """
    if dark_mode:
        return """
/* 暗色主题 */
QMainWindow {
    background-color: #2b2b2b;
    color: #ffffff;
}

QWidget {
    background-color: #2b2b2b;
    color: #ffffff;
}

QPushButton {
    background-color: #3d3d3d;
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 5px 15px;
}

QPushButton:hover {
    background-color: #4d4d4d;
}

QPushButton:pressed {
    background-color: #555555;
}

QLineEdit {
    background-color: #3d3d3d;
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 5px;
}

QTextEdit {
    background-color: #3d3d3d;
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 4px;
}

QProgressBar {
    border: 1px solid #555555;
    border-radius: 4px;
    text-align: center;
    background-color: #3d3d3d;
}

QProgressBar::chunk {
    background-color: #3daee9;
    width: 1px;
}

QMenuBar {
    background-color: #2b2b2b;
    color: #ffffff;
}

QMenuBar::item {
    background-color: transparent;
}

QMenuBar::item:selected {
    background-color: #3daee9;
}

QMenu {
    background-color: #2b2b2b;
    color: #ffffff;
    border: 1px solid #555555;
}

QMenu::item:selected {
    background-color: #3daee9;
}

QStatusBar {
    background-color: #2b2b2b;
    color: #ffffff;
}
"""
    else:
        return """
/* 亮色主题 */
QMainWindow {
    background-color: #f0f0f0;
    color: #000000;
}

QWidget {
    background-color: #f0f0f0;
    color: #000000;
}

QPushButton {
    background-color: #e0e0e0;
    color: #000000;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
    padding: 5px 15px;
}

QPushButton:hover {
    background-color: #d0d0d0;
}

QPushButton:pressed {
    background-color: #c0c0c0;
}

QLineEdit {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
    padding: 5px;
}

QTextEdit {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #c0c0c0;
    border-radius: 4px;
}

QProgressBar {
    border: 1px solid #c0c0c0;
    border-radius: 4px;
    text-align: center;
    background-color: #ffffff;
}

QProgressBar::chunk {
    background-color: #3daee9;
    width: 1px;
}

QMenuBar {
    background-color: #f0f0f0;
    color: #000000;
}

QMenuBar::item {
    background-color: transparent;
}

QMenuBar::item:selected {
    background-color: #3daee9;
}

QMenu {
    background-color: #f0f0f0;
    color: #000000;
    border: 1px solid #c0c0c0;
}

QMenu::item:selected {
    background-color: #3daee9;
}

QStatusBar {
    background-color: #f0f0f0;
    color: #000000;
}
"""

class ThemeManager:
    """主题管理器。
    
    管理应用程序的主题设置。
    支持暗色/亮色主题切换。
    
    Attributes:
        settings: QSettings, 应用程序设置
        dark_mode: bool, 是否为暗色主题
    """
    
    def __init__(self):
        """初始化主题管理器。"""
        self.settings = QSettings()
        self.dark_mode = self.settings.value("theme/dark_mode", False, type=bool)
        
    def switch_dark_mode(self, enable: bool) -> None:
        """切换暗色主题。
        
        Args:
            enable: 是否启用暗色主题
        """
        try:
            # 保存设置
            self.dark_mode = enable
            self.settings.setValue("theme/dark_mode", enable)
            
            # 获取应用程序实例
            app = QApplication.instance()
            if not app:
                return
                
            # 加载并应用样式表
            style = load_style(enable)
            app.setStyleSheet(style)
            
            # 更新调色板
            palette = QPalette()
            if enable:
                # 暗色主题颜色
                palette.setColor(QPalette.Window, QColor(53, 53, 53))
                palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
                palette.setColor(QPalette.Base, QColor(25, 25, 25))
                palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
                palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
                palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
                palette.setColor(QPalette.Text, QColor(255, 255, 255))
                palette.setColor(QPalette.Button, QColor(53, 53, 53))
                palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
                palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
                palette.setColor(QPalette.Link, QColor(42, 130, 218))
                palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
                palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
            else:
                # 亮色主题颜色
                palette = app.style().standardPalette()
                
            # 应用调色板
            app.setPalette(palette)
            
            # 强制刷新所有控件
            for widget in app.allWidgets():
                # 更新调色板
                widget.setPalette(palette)
                # 更新样式表
                widget.setStyleSheet(widget.styleSheet())
                # 强制重绘
                widget.update()
                
            logger.info(f"主题切换{'成功' if enable else '关闭'}")
            
        except Exception as e:
            logger.error(f"切换主题失败: {str(e)}")
            
    def apply_theme(self) -> None:
        """应用当前主题设置。"""
        self.switch_dark_mode(self.dark_mode) 