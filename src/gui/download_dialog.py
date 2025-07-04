"""下载对话框模块。

提供视频下载选项配置界面。
支持格式选择和下载参数设置。
"""

import logging
from typing import Dict, Any, List, Optional
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
    QFileDialog
)
from PySide6.QtCore import Qt, Signal

logger = logging.getLogger(__name__)

class DownloadDialog(QDialog):
    """下载配置对话框。
    
    用于配置下载参数：
    - 保存目录
    - 最大下载视频数
    """
    
    def __init__(self, parent=None):
        """初始化对话框。
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.setWindowTitle("下载配置")
        self.setModal(True)
        
        # 创建布局
        layout = QVBoxLayout(self)
        
        # 保存目录选择
        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("选择保存目录")
        self.dir_input.setText(str(Path.home() / "Downloads"))
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self._browse_directory)
        dir_layout.addWidget(QLabel("保存目录:"))
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.browse_btn)
        layout.addLayout(dir_layout)
        
        # 最大视频数设置
        max_videos_layout = QHBoxLayout()
        self.max_videos_input = QSpinBox()
        self.max_videos_input.setRange(0, 10000)
        self.max_videos_input.setValue(0)
        self.max_videos_input.setSpecialValueText("无限制")
        max_videos_layout.addWidget(QLabel("最大视频数:"))
        max_videos_layout.addWidget(self.max_videos_input)
        layout.addLayout(max_videos_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
        
    def _browse_directory(self):
        """浏览并选择保存目录。"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            self.dir_input.text(),
            QFileDialog.ShowDirsOnly
        )
        if directory:
            self.dir_input.setText(directory)
            
    def get_save_dir(self) -> str:
        """获取保存目录。
        
        Returns:
            str: 保存目录路径
        """
        return self.dir_input.text()
        
    def get_max_videos(self) -> int:
        """获取最大视频数。
        
        Returns:
            int: 最大视频数，0表示无限制
        """
        return self.max_videos_input.value()

    def _setup_ui(self):
        """设置用户界面。"""
        self.setWindowTitle("下载选项")
        self.setMinimumWidth(400)
        
        # 创建主布局
        layout = QVBoxLayout(self)
        
        # 格式选择组
        format_group = QGroupBox("格式选择")
        format_layout = QFormLayout()
        
        # 视频格式选择
        self.format_combo = QComboBox()
        self._populate_formats()
        format_layout.addRow("视频格式:", self.format_combo)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # 下载选项组
        options_group = QGroupBox("下载选项")
        options_layout = QFormLayout()
        
        # 保存目录
        save_layout = QHBoxLayout()
        self.save_path = QLineEdit()
        self.save_path.setReadOnly(True)
        self.save_path.setPlaceholderText("选择保存目录...")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_directory)
        save_layout.addWidget(self.save_path)
        save_layout.addWidget(browse_btn)
        options_layout.addRow("保存目录:", save_layout)
        
        # 字幕选项
        self.subtitle_check = QCheckBox("下载字幕")
        self.subtitle_check.setChecked(True)
        options_layout.addRow("字幕:", self.subtitle_check)
        
        # 字幕语言
        self.subtitle_lang = QComboBox()
        self.subtitle_lang.addItems(["中文", "英文", "全部"])
        self.subtitle_lang.setCurrentText("中文")
        options_layout.addRow("字幕语言:", self.subtitle_lang)
        
        # 视频封面
        self.thumbnail_check = QCheckBox("下载封面")
        self.thumbnail_check.setChecked(True)
        options_layout.addRow("封面:", self.thumbnail_check)
        
        # 视频信息
        self.info_check = QCheckBox("保存视频信息")
        self.info_check.setChecked(True)
        options_layout.addRow("视频信息:", self.info_check)
        
        # 重试次数
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(3)
        options_layout.addRow("重试次数:", self.retry_spin)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # 代理设置组
        proxy_group = QGroupBox("代理设置")
        proxy_layout = QFormLayout()
        
        # 代理开关
        self.proxy_check = QCheckBox("使用代理")
        self.proxy_check.setChecked(True)
        proxy_layout.addRow("启用:", self.proxy_check)
        
        # 代理地址
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setText("http://127.0.0.1:7890")
        proxy_layout.addRow("地址:", self.proxy_edit)
        
        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)
        
        # 确定取消按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def _populate_formats(self):
        """填充格式选择框。"""
        if not self.formats:
            # 添加默认格式
            default_formats = [
                {"label": "最佳质量", "format_id": "bestvideo+bestaudio"},
                {"label": "1080P", "format_id": "137+140"},
                {"label": "720P", "format_id": "136+140"},
                {"label": "480P", "format_id": "135+140"},
                {"label": "360P", "format_id": "134+140"}
            ]
            for fmt in default_formats:
                self.format_combo.addItem(
                    fmt["label"],
                    userData=fmt["format_id"]
                )
        else:
            # 添加可用格式
            for fmt in self.formats:
                label = fmt.get("label", fmt.get("format_id", "未知格式"))
                self.format_combo.addItem(
                    label,
                    userData=fmt.get("format_id")
                )
                
    def get_options(self) -> Dict[str, Any]:
        """获取下载选项。
        
        Returns:
            Dict[str, Any]: 下载选项字典
        """
        return {
            "format": self.format_combo.currentData(),
            "save_dir": self.save_path.text() or "downloads",
            "subtitles": self.subtitle_check.isChecked(),
            "subtitle_language": self.subtitle_lang.currentText(),
            "thumbnail": self.thumbnail_check.isChecked(),
            "write_info": self.info_check.isChecked(),
            "max_retries": self.retry_spin.value(),
            "proxy": {
                "enabled": self.proxy_check.isChecked(),
                "url": self.proxy_edit.text()
            }
        }
        
    def accept(self):
        """确认对话框。"""
        try:
            options = self.get_options()
            self.options_selected.emit(options)
            logger.info(f"下载选项已确认: {options}")
            super().accept()
        except Exception as e:
            logger.error(f"处理下载选项时出错: {str(e)}")
            
    @classmethod
    def get_download_options(
        cls,
        formats: Optional[List[Dict[str, Any]]] = None,
        parent=None
    ) -> Optional[Dict[str, Any]]:
        """显示下载对话框并获取选项。
        
        Args:
            formats: 可用的下载格式列表
            parent: 父窗口
            
        Returns:
            Optional[Dict[str, Any]]: 下载选项，如果用户取消则返回None
        """
        dialog = cls(parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_options()
        return None 