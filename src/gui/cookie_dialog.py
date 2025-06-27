"""Cookie 管理对话框模块。

提供 Cookie 管理界面，支持：
- 查看当前 Cookie 状态
- 从浏览器同步 Cookie
- 手动编辑 Cookie
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QMessageBox,
    QComboBox,
    QTabWidget,
    QWidget,
    QFormLayout,
    QLineEdit,
    QFileDialog,
    QCheckBox
)
from PySide6.QtCore import Qt

from src.utils.cookie_manager import CookieManager
from src.tools.sync_cookies import sync_twitter_cookies, sync_youtube_cookies

logger = logging.getLogger(__name__)

def _convert_cookie_format(text: str) -> Dict[str, str]:
    """转换Cookie格式。
    
    支持以下格式：
    1. JSON格式: {"name": "value", ...}
    2. Cookie字符串格式: name=value; name2=value2
    3. Cookie-Editor导出格式: [{name: "name", value: "value"}, ...]
    
    Args:
        text: Cookie文本
        
    Returns:
        Dict[str, str]: Cookie字典
        
    Raises:
        ValueError: 格式无效
    """
    text = text.strip()
    cookies = {}
    
    try:
        # 尝试解析JSON格式
        if text.startswith("{"):
            # 标准JSON格式
            return json.loads(text)
        elif text.startswith("["):
            # Cookie-Editor格式
            cookie_list = json.loads(text)
            if not isinstance(cookie_list, list):
                raise ValueError("无效的Cookie-Editor格式")
            for cookie in cookie_list:
                if isinstance(cookie, dict) and "name" in cookie and "value" in cookie:
                    cookies[cookie["name"]] = cookie["value"]
            return cookies
        else:
            # Cookie字符串格式
            pairs = text.split(";")
            for pair in pairs:
                if "=" in pair:
                    name, value = pair.split("=", 1)
                    cookies[name.strip()] = value.strip()
            return cookies
    except Exception as e:
        raise ValueError(
            "Cookie格式无效。支持的格式：\n"
            "1. JSON格式：{\"name\": \"value\", ...}\n"
            "2. Cookie字符串：name=value; name2=value2\n"
            "3. Cookie-Editor格式：[{\"name\": \"name\", \"value\": \"value\"}, ...]\n"
            f"错误详情：{str(e)}"
        )

class CookieDialog(QDialog):
    """Cookie 管理对话框。"""
    
    def __init__(
        self,
        platform: str,
        cookie_manager: Optional[CookieManager] = None,
        parent=None
    ):
        """初始化对话框。"""
        super().__init__(parent)
        self.platform = platform
        self.cookie_manager = cookie_manager or CookieManager()
        
        # 设置窗口属性
        self.setWindowTitle(f"{platform.title()} 账号管理")
        self.resize(600, 500)
        
        # 创建界面
        self._setup_ui()
        
        # 加载当前 Cookie
        self.load_cookies()
        
    def _setup_ui(self):
        """创建界面元素。"""
        layout = QVBoxLayout()
        
        # 状态区域
        status_layout = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setStyleSheet(
            "QLabel { padding: 5px; border-radius: 3px; }"
        )
        status_layout.addWidget(self.status_label)
        
        # 添加帮助按钮
        help_btn = QPushButton("格式说明")
        help_btn.clicked.connect(self._show_format_help)
        status_layout.addWidget(help_btn)
        
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # 创建标签页
        tab_widget = QTabWidget()
        
        # 浏览器同步标签页
        browser_tab = QWidget()
        browser_layout = QVBoxLayout(browser_tab)
        
        # 浏览器选择
        browser_form = QFormLayout()
        self.browser_combo = QComboBox()
        self.browser_combo.addItems([
            "Chrome",
            "Firefox",
            "Edge",
            "Brave",
            "Opera",
            "Vivaldi",
            "Chromium",
            "Cent"
        ])
        browser_form.addRow("选择浏览器:", self.browser_combo)
        
        # 自定义路径
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("浏览器数据目录路径（可选）")
        self.select_path_btn = QPushButton("选择目录")
        self.select_path_btn.clicked.connect(self._select_browser_path)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.select_path_btn)
        browser_form.addRow("数据目录:", path_layout)
        
        browser_layout.addLayout(browser_form)
        
        # 同步按钮
        self.sync_btn = QPushButton("从浏览器同步")
        self.sync_btn.clicked.connect(self._sync_from_browser)
        browser_layout.addWidget(self.sync_btn)
        browser_layout.addStretch()
        
        tab_widget.addTab(browser_tab, "浏览器同步")
        
        # 手动输入标签页
        manual_tab = QWidget()
        manual_layout = QVBoxLayout(manual_tab)
        
        # Cookie编辑区域
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "在此处粘贴或编辑 Cookie\n"
            "支持以下格式：\n"
            "1. JSON格式：\n"
            "{\n"
            '    "auth_token": "xxx",\n'
            '    "ct0": "xxx"\n'
            "}\n\n"
            "2. Cookie字符串格式：\n"
            "auth_token=xxx; ct0=xxx\n\n"
            "3. Cookie-Editor格式：\n"
            "[\n"
            "    {\n"
            '        "name": "auth_token",\n'
            '        "value": "xxx"\n'
            "    }\n"
            "]"
        )
        manual_layout.addWidget(self.text_edit)
        
        # 保存按钮
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self._save_cookies)
        manual_layout.addWidget(self.save_btn)
        
        tab_widget.addTab(manual_tab, "手动输入")
        
        layout.addWidget(tab_widget)
        
        # 关闭按钮
        button_layout = QHBoxLayout()
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def _select_browser_path(self):
        """选择浏览器数据目录。"""
        path = QFileDialog.getExistingDirectory(
            self,
            "选择浏览器数据目录",
            str(Path.home())
        )
        if path:
            self.path_input.setText(path)
            
    def load_cookies(self):
        """加载当前 Cookie。"""
        try:
            cookies = self.cookie_manager.get_cookies(self.platform)
            if cookies:
                if hasattr(self, 'text_edit'):
                    self.text_edit.setText(
                        json.dumps(cookies, indent=2, ensure_ascii=False)
                    )
                self._update_status(True)
            else:
                self._update_status(False)
        except Exception as e:
            logger.error(f"加载 Cookie 失败: {e}")
            self._update_status(False)
            
    def _update_status(self, valid: bool):
        """更新状态标签。
        
        Args:
            valid: Cookie 是否有效
        """
        if valid:
            self.status_label.setText("✅ 已登录")
            self.status_label.setStyleSheet(
                "QLabel { background-color: #dff0d8; color: #3c763d; "
                "padding: 5px; border-radius: 3px; }"
            )
        else:
            self.status_label.setText("❌ 未登录")
            self.status_label.setStyleSheet(
                "QLabel { background-color: #f2dede; color: #a94442; "
                "padding: 5px; border-radius: 3px; }"
            )
            
    def _validate_json(self, text: str) -> Optional[Dict]:
        """验证 Cookie 格式。
        
        Args:
            text: Cookie 文本
            
        Returns:
            Optional[Dict]: 解析后的字典，如果格式无效则返回 None
        """
        try:
            return _convert_cookie_format(text)
        except ValueError as e:
            QMessageBox.warning(
                self,
                "格式错误",
                str(e)
            )
            return None
            
    def _show_format_help(self):
        """显示格式帮助对话框。"""
        help_text = (
            "支持的Cookie格式：\n\n"
            "1. JSON格式：\n"
            "{\n"
            '    "auth_token": "xxx",\n'
            '    "ct0": "xxx"\n'
            "}\n\n"
            "2. Cookie字符串格式：\n"
            "auth_token=xxx; ct0=xxx\n\n"
            "3. Cookie-Editor格式：\n"
            "[\n"
            "    {\n"
            '        "name": "auth_token",\n'
            '        "value": "xxx"\n'
            "    }\n"
            "]"
        )
        
        QMessageBox.information(
            self,
            "Cookie格式说明",
            help_text
        )
            
    def _sync_from_browser(self):
        """从浏览器同步 Cookie。"""
        try:
            browser = self.browser_combo.currentText().lower()
            browser_path = self.path_input.text().strip() or None
            
            sync_func = {
                "twitter": sync_twitter_cookies,
                "youtube": sync_youtube_cookies
            }.get(self.platform)
            
            if not sync_func:
                raise ValueError(f"不支持的平台: {self.platform}")
                
            if sync_func(browsers=[browser], browser_path=browser_path):
                self.load_cookies()
                QMessageBox.information(
                    self,
                    "同步成功",
                    f"已从 {browser} 同步 Cookie"
                )
                self.accept()  # 关闭对话框
            else:
                QMessageBox.warning(
                    self,
                    "同步失败",
                    f"从 {browser} 同步 Cookie 失败\n"
                    f"请确保已登录 {self.platform.title()}"
                )
        except Exception as e:
            logger.error(f"同步 Cookie 失败: {e}")
            QMessageBox.critical(
                self,
                "同步错误",
                f"同步 Cookie 时出错: {e}"
            )
            
    def _save_cookies(self):
        """保存 Cookie。"""
        try:
            text = self.text_edit.toPlainText().strip()
            if not text:
                QMessageBox.warning(
                    self,
                    "保存失败",
                    "Cookie 内容不能为空"
                )
                return
                
            data = self._validate_json(text)
            if data is None:
                return
                
            # 保存到 Cookie 管理器
            self.cookie_manager.save_cookies(self.platform, data)
            
            QMessageBox.information(
                self,
                "保存成功",
                "Cookie 已保存"
            )
            self._update_status(True)
            self.accept()  # 关闭对话框
            
        except Exception as e:
            logger.error(f"保存 Cookie 失败: {e}")
            QMessageBox.critical(
                self,
                "保存错误",
                f"保存 Cookie 时出错: {e}"
            ) 