"""帮助对话框模块。

提供操作指南界面。
"""

from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextBrowser,
    QPushButton,
    QWidget
)
from PySide6.QtCore import Qt

class HelpDialog(QDialog):
    """帮助对话框。
    
    显示以下内容：
    1. 基本操作指南
    2. 高级功能说明
    3. 常见问题解答
    4. 故障排除指南
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        """初始化帮助对话框。
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.setWindowTitle("帮助")
        self.setMinimumSize(600, 400)
        
        # 创建界面
        self._create_ui()
        
    def _create_ui(self):
        """创建界面。"""
        layout = QVBoxLayout()
        
        # 帮助内容
        help_text = QTextBrowser()
        help_text.setOpenExternalLinks(True)
        help_text.setHtml(self._get_help_content())
        layout.addWidget(help_text)
        
        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        
        self.setLayout(layout)
        
    def _get_help_content(self) -> str:
        """获取帮助内容。
        
        Returns:
            str: 帮助内容HTML
        """
        return """
        <h1>视频下载器使用指南</h1>
        
        <h2>目录</h2>
        <ul>
            <li><a href="#basic">基本操作</a></li>
            <li><a href="#advanced">高级功能</a></li>
            <li><a href="#faq">常见问题</a></li>
            <li><a href="#troubleshooting">故障排除</a></li>
        </ul>
        
        <h2 id="basic">基本操作</h2>
        <h3>1. 添加下载任务</h3>
        <ol>
            <li>复制视频页面URL</li>
            <li>点击"添加"按钮或使用快捷键Ctrl+N</li>
            <li>在弹出的对话框中粘贴URL</li>
            <li>选择保存目录（可选）</li>
            <li>点击"确定"开始下载</li>
        </ol>
        
        <h3>2. 管理下载任务</h3>
        <ul>
            <li>暂停/继续：点击任务右侧的暂停/继续按钮</li>
            <li>取消：点击任务右侧的取消按钮</li>
            <li>清除：右键点击任务，选择"清除"</li>
            <li>打开文件：双击已完成的任务</li>
        </ul>
        
        <h2 id="advanced">高级功能</h2>
        <h3>1. 下载设置</h3>
        <ul>
            <li>最大并发数：同时下载的最大任务数</li>
            <li>超时时间：单个请求的最长等待时间</li>
            <li>重试次数：下载失败时的重试次数</li>
            <li>块大小：每次读取的数据大小</li>
            <li>缓冲区大小：写入文件的缓冲区大小</li>
        </ul>
        
        <h3>2. 网络设置</h3>
        <ul>
            <li>代理设置：支持HTTP和SOCKS代理</li>
            <li>请求头：自定义HTTP请求头</li>
            <li>Cookie：网站登录凭证</li>
        </ul>
        
        <h3>3. 缓存设置</h3>
        <ul>
            <li>内存缓存：加快访问速度</li>
            <li>文件缓存：持久化存储</li>
            <li>过期时间：缓存自动失效时间</li>
        </ul>
        
        <h2 id="faq">常见问题</h2>
        <h3>1. 下载速度慢</h3>
        <p>可能的原因：</p>
        <ul>
            <li>网络连接不稳定</li>
            <li>服务器限制下载速度</li>
            <li>代理服务器速度慢</li>
        </ul>
        <p>解决方法：</p>
        <ul>
            <li>检查网络连接</li>
            <li>尝试使用其他代理</li>
            <li>减少并发下载数量</li>
        </ul>
        
        <h3>2. 下载失败</h3>
        <p>可能的原因：</p>
        <ul>
            <li>视频已删除或私有</li>
            <li>需要登录才能访问</li>
            <li>地区限制</li>
        </ul>
        <p>解决方法：</p>
        <ul>
            <li>确认视频是否可以正常访问</li>
            <li>添加登录Cookie</li>
            <li>使用代理绕过限制</li>
        </ul>
        
        <h2 id="troubleshooting">故障排除</h2>
        <h3>1. 检查日志</h3>
        <p>日志文件位于：</p>
        <ul>
            <li>Windows: %APPDATA%/VideoDownloader/logs</li>
            <li>Linux: ~/.config/VideoDownloader/logs</li>
            <li>macOS: ~/Library/Logs/VideoDownloader</li>
        </ul>
        
        <h3>2. 常见错误代码</h3>
        <table border="1">
            <tr>
                <th>错误代码</th>
                <th>说明</th>
                <th>解决方法</th>
            </tr>
            <tr>
                <td>E001</td>
                <td>网络连接失败</td>
                <td>检查网络连接，尝试使用代理</td>
            </tr>
            <tr>
                <td>E002</td>
                <td>认证失败</td>
                <td>检查Cookie是否正确</td>
            </tr>
            <tr>
                <td>E003</td>
                <td>解析失败</td>
                <td>检查URL是否正确，更新解析规则</td>
            </tr>
        </table>
        
        <h3>3. 联系支持</h3>
        <p>如果遇到无法解决的问题，请通过以下方式联系我们：</p>
        <ul>
            <li>GitHub Issues: <a href="https://github.com/your-repo/issues">https://github.com/your-repo/issues</a></li>
            <li>Email: support@example.com</li>
        </ul>
        """ 