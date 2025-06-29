"""帮助对话框模块。

提供应用程序的帮助信息和使用说明。
"""

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextBrowser,
    QPushButton,
    QDialogButtonBox
)
from PySide6.QtCore import Qt

class HelpDialog(QDialog):
    """帮助对话框。
    
    显示应用程序的帮助信息，包括：
    1. 基本使用说明
    2. 支持的平台
    3. 常见问题解答
    4. 快捷键说明
    """
    
    def __init__(self, parent=None):
        """初始化帮助对话框。
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.setWindowTitle("帮助")
        self.setMinimumSize(600, 400)
        
        # 创建界面
        self._setup_ui()
        
        # 加载帮助内容
        self._load_help_content()
        
    def _setup_ui(self):
        """创建界面。"""
        # 主布局
        layout = QVBoxLayout(self)
        
        # 帮助内容
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        layout.addWidget(self.text_browser)
        
        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok,
            Qt.Horizontal
        )
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
        
    def _load_help_content(self):
        """加载帮助内容。"""
        help_text = """
        <h2>视频下载器使用说明</h2>
        
        <h3>基本使用</h3>
        <p>1. 复制视频链接</p>
        <p>2. 点击"新建下载"按钮或使用快捷键 Ctrl+N</p>
        <p>3. 粘贴链接并选择保存目录</p>
        <p>4. 点击"开始下载"</p>
        
        <h3>支持的平台</h3>
        <ul>
            <li>Xvideos</li>
            <li>Tumblr</li>
            <li>更多平台持续添加中...</li>
        </ul>
        
        <h3>常见问题</h3>
        <p><b>Q: 下载速度很慢怎么办？</b></p>
        <p>A: 可以尝试以下方法：</p>
        <ul>
            <li>检查网络连接</li>
            <li>使用代理服务器</li>
            <li>调整同时下载数量</li>
        </ul>
        
        <p><b>Q: 提示需要登录怎么办？</b></p>
        <p>A: 某些内容需要登录才能访问，您可以：</p>
        <ul>
            <li>从浏览器导入 Cookie</li>
            <li>手动设置 Cookie</li>
        </ul>
        
        <h3>快捷键</h3>
        <table border="1" cellspacing="0" cellpadding="5">
            <tr>
                <th>功能</th>
                <th>快捷键</th>
            </tr>
            <tr>
                <td>新建下载</td>
                <td>Ctrl+N</td>
            </tr>
            <tr>
                <td>开始所有</td>
                <td>Ctrl+S</td>
            </tr>
            <tr>
                <td>暂停所有</td>
                <td>Ctrl+P</td>
            </tr>
            <tr>
                <td>删除选中</td>
                <td>Delete</td>
            </tr>
            <tr>
                <td>清空已完成</td>
                <td>Ctrl+C</td>
            </tr>
            <tr>
                <td>打开设置</td>
                <td>Ctrl+,</td>
            </tr>
            <tr>
                <td>显示帮助</td>
                <td>F1</td>
            </tr>
        </table>
        
        <h3>注意事项</h3>
        <ul>
            <li>请确保有足够的磁盘空间</li>
            <li>建议使用稳定的网络连接</li>
            <li>部分平台可能需要科学上网</li>
            <li>遵守相关法律法规</li>
        </ul>
        """
        
        self.text_browser.setHtml(help_text) 