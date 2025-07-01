"""创作者监控对话框。"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox
)
from PySide6.QtCore import Qt
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class CreatorMonitorDialog(QDialog):
    """创作者监控对话框。"""
    
    def __init__(self, settings: Dict[str, Any], parent=None):
        """初始化对话框。
        
        Args:
            settings: 配置信息
            parent: 父窗口
        """
        super().__init__(parent)
        self.settings = settings
        self._setup_ui()
        self._load_creators()
        
    def _setup_ui(self):
        """创建界面。"""
        self.setWindowTitle("创作者监控")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                font-size: 14px;
            }
            QLineEdit, QComboBox {
                padding: 5px;
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                background-color: #1890ff;
                color: white;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
            QPushButton:pressed {
                background-color: #096dd9;
            }
            QPushButton[flat=true] {
                background-color: transparent;
                color: #1890ff;
            }
            QPushButton[flat=true]:hover {
                color: #40a9ff;
            }
            QTableWidget {
                border: none;
                background-color: white;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #e6f7ff;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 添加创作者
        add_layout = QHBoxLayout()
        
        # 平台选择
        platform_label = QLabel("平台")
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(['YouTube', 'Twitter', 'Bilibili'])
        
        # 创作者ID
        creator_label = QLabel("创作者ID")
        self.creator_edit = QLineEdit()
        
        # 添加按钮
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_creator)
        
        add_layout.addWidget(platform_label)
        add_layout.addWidget(self.platform_combo)
        add_layout.addWidget(creator_label)
        add_layout.addWidget(self.creator_edit)
        add_layout.addWidget(add_btn)
        
        # 创作者列表
        self.creator_table = QTableWidget()
        self.creator_table.setColumnCount(4)
        self.creator_table.setHorizontalHeaderLabels(['平台', '创作者ID', '最新视频', '操作'])
        self.creator_table.horizontalHeader().setStretchLastSection(True)
        self.creator_table.verticalHeader().setVisible(False)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        close_btn = QPushButton("关闭")
        close_btn.setFlat(True)
        close_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save_creators)
        
        button_layout.addWidget(close_btn)
        button_layout.addWidget(save_btn)
        
        # 添加到主布局
        layout.addLayout(add_layout)
        layout.addWidget(self.creator_table)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def _load_creators(self):
        """加载创作者列表。"""
        try:
            creators = self.settings.get('monitor.creators', [])
            
            self.creator_table.setRowCount(len(creators))
            
            for i, creator in enumerate(creators):
                # 平台
                platform_item = QTableWidgetItem(creator['platform'])
                platform_item.setFlags(platform_item.flags() & ~Qt.ItemIsEditable)
                self.creator_table.setItem(i, 0, platform_item)
                
                # 创作者ID
                creator_item = QTableWidgetItem(creator['id'])
                creator_item.setFlags(creator_item.flags() & ~Qt.ItemIsEditable)
                self.creator_table.setItem(i, 1, creator_item)
                
                # 最新视频
                video_item = QTableWidgetItem(creator.get('latest_video', ''))
                video_item.setFlags(video_item.flags() & ~Qt.ItemIsEditable)
                self.creator_table.setItem(i, 2, video_item)
                
                # 删除按钮
                delete_btn = QPushButton("删除")
                delete_btn.setFlat(True)
                delete_btn.clicked.connect(lambda _, row=i: self._delete_creator(row))
                self.creator_table.setCellWidget(i, 3, delete_btn)
                
        except Exception as e:
            logger.error(f"加载创作者列表失败: {e}")
            
    def _add_creator(self):
        """添加创作者。"""
        try:
            platform = self.platform_combo.currentText()
            creator_id = self.creator_edit.text().strip()
            
            if not creator_id:
                QMessageBox.warning(self, "错误", "请输入创作者ID")
                return
                
            # 添加到列表
            row = self.creator_table.rowCount()
            self.creator_table.insertRow(row)
            
            # 平台
            platform_item = QTableWidgetItem(platform)
            platform_item.setFlags(platform_item.flags() & ~Qt.ItemIsEditable)
            self.creator_table.setItem(row, 0, platform_item)
            
            # 创作者ID
            creator_item = QTableWidgetItem(creator_id)
            creator_item.setFlags(creator_item.flags() & ~Qt.ItemIsEditable)
            self.creator_table.setItem(row, 1, creator_item)
            
            # 最新视频
            video_item = QTableWidgetItem('')
            video_item.setFlags(video_item.flags() & ~Qt.ItemIsEditable)
            self.creator_table.setItem(row, 2, video_item)
            
            # 删除按钮
            delete_btn = QPushButton("删除")
            delete_btn.setFlat(True)
            delete_btn.clicked.connect(lambda _, row=row: self._delete_creator(row))
            self.creator_table.setCellWidget(row, 3, delete_btn)
            
            # 清空输入
            self.creator_edit.clear()
            
        except Exception as e:
            logger.error(f"添加创作者失败: {e}")
            
    def _delete_creator(self, row: int):
        """删除创作者。
        
        Args:
            row: 行号
        """
        try:
            self.creator_table.removeRow(row)
            
        except Exception as e:
            logger.error(f"删除创作者失败: {e}")
            
    def _save_creators(self):
        """保存创作者列表。"""
        try:
            creators = []
            
            for i in range(self.creator_table.rowCount()):
                creator = {
                    'platform': self.creator_table.item(i, 0).text(),
                    'id': self.creator_table.item(i, 1).text(),
                    'latest_video': self.creator_table.item(i, 2).text()
                }
                creators.append(creator)
                
            self.settings.set('monitor.creators', creators)
            self.accept()
            
        except Exception as e:
            logger.error(f"保存创作者列表失败: {e}")
            QMessageBox.critical(self, "错误", f"保存创作者列表失败: {e}") 