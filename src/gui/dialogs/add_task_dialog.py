"""添加任务对话框模块。

提供添加下载任务的界面。
"""

from typing import Dict, Any, Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QComboBox,
    QFormLayout,
    QSpinBox,
    QMessageBox,
    QWidget
)
from PySide6.QtCore import Qt, Signal

class AddTaskDialog(QDialog):
    """添加任务对话框。
    
    提供以下功能：
    1. 输入下载URL
    2. 选择保存目录
    3. 选择下载器类型
    4. 设置下载参数
    
    Signals:
        task_added: 任务添加信号
    """
    
    task_added = Signal(dict)
    
    def __init__(
        self,
        settings: Dict[str, Any],
        parent: Optional[QWidget] = None
    ):
        """初始化添加任务对话框。
        
        Args:
            settings: 配置信息
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.settings = settings
        self._url = ""
        self._save_dir = ""
        self._platform = ""
        
        self.setWindowTitle("添加下载任务")
        self.setMinimumWidth(500)
        
        # 创建界面
        self._create_ui()
        
    def _create_ui(self):
        """创建界面。"""
        layout = QVBoxLayout()
        
        # 创建表单
        form_layout = QFormLayout()
        
        # URL输入框
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("请输入视频URL")
        form_layout.addRow("下载URL:", self.url_edit)
        
        # 平台选择
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["pornhub", "twitter"])
        form_layout.addRow("平台:", self.platform_combo)
        
        # 保存目录
        save_dir_layout = QHBoxLayout()
        self.save_dir_edit = QLineEdit()
        self.save_dir_edit.setText(str(self.settings.get('save_dir', '')))
        browse_button = QPushButton("浏览")
        browse_button.clicked.connect(self._browse_save_dir)
        save_dir_layout.addWidget(self.save_dir_edit)
        save_dir_layout.addWidget(browse_button)
        form_layout.addRow("保存目录:", save_dir_layout)
        
        # 下载器选择
        self.downloader_combo = QComboBox()
        self.downloader_combo.addItems([
            "自动选择",
            "YouTube",
            "Twitter",
            "Bilibili",
            "抖音",
            "快手"
        ])
        form_layout.addRow("下载器:", self.downloader_combo)
        
        # 优先级
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 10)
        self.priority_spin.setValue(5)
        form_layout.addRow("优先级:", self.priority_spin)
        
        # 速度限制
        self.speed_limit_spin = QSpinBox()
        self.speed_limit_spin.setRange(0, 10240)
        self.speed_limit_spin.setSuffix(" KB/s")
        self.speed_limit_spin.setSpecialValueText("不限制")
        form_layout.addRow("速度限制:", self.speed_limit_spin)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self._add_task)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def _browse_save_dir(self):
        """浏览保存目录。"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            self.save_dir_edit.text()
        )
        if dir_path:
            self.save_dir_edit.setText(dir_path)
            
    def _add_task(self):
        """添加下载任务。"""
        # 获取输入
        self._url = self.url_edit.text().strip()
        self._save_dir = self.save_dir_edit.text().strip()
        self._platform = self.platform_combo.currentText()
        downloader = self.downloader_combo.currentText()
        priority = self.priority_spin.value()
        speed_limit = (
            self.speed_limit_spin.value() * 1024
            if self.speed_limit_spin.value() > 0
            else None
        )
        
        # 验证输入
        if not self._url:
            QMessageBox.warning(self, "错误", "请输入下载URL")
            return
            
        if not self._save_dir:
            QMessageBox.warning(self, "错误", "请选择保存目录")
            return
            
        # 创建任务参数
        task_params = {
            'url': self._url,
            'save_dir': Path(self._save_dir),
            'platform': self._platform,
            'downloader': downloader,
            'priority': priority,
            'speed_limit': speed_limit
        }
        
        # 发送信号
        self.task_added.emit(task_params)
        
        # 关闭对话框
        self.accept()
        
    def get_task_params(self) -> Dict[str, Any]:
        """获取任务参数。
        
        Returns:
            Dict[str, Any]: 任务参数字典，包含：
                - url: 下载URL
                - save_dir: 保存路径
                - platform: 平台标识
        """
        return {
            'url': self._url,
            'save_dir': self._save_dir,
            'platform': self._platform
        } 