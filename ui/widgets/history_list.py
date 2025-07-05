"""历史记录列表组件"""

from typing import List, Optional
from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QMenu,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QContextMenuEvent

from core.history import HistoryManager

class HistoryListItem(QListWidgetItem):
    """历史记录列表项"""
    
    def __init__(self, record_id: int, url: str, title: str, date: str):
        """初始化列表项
        
        Args:
            record_id: 记录ID
            url: 视频URL
            title: 视频标题
            date: 下载日期
        """
        super().__init__()
        self.record_id = record_id
        self.url = url
        self.title = title
        self.date = date
        
        # 设置显示文本
        self.setText(f"{title}\n{url}\n{date}")
        
        # 设置工具提示
        self.setToolTip(f"标题: {title}\nURL: {url}\n日期: {date}")
        
class HistoryList(QListWidget):
    """历史记录列表"""
    
    item_deleted = Signal(int)  # 记录删除信号
    
    def __init__(self, history_manager: HistoryManager):
        """初始化列表
        
        Args:
            history_manager: 历史记录管理器实例
        """
        super().__init__()
        self.history_manager = history_manager
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        # 设置列表属性
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setSpacing(2)
        self.setWordWrap(True)
        
        # 加载初始数据
        self.load_records()
        
    def load_records(self):
        """加载历史记录"""
        self.clear()
        records = self.history_manager.get_all_records()
        
        for record in records:
            record_id, url, title, date, _ = record
            item = HistoryListItem(record_id, url, title, date)
            self.addItem(item)
            
    def delete_selected(self) -> bool:
        """删除选中的记录
        
        Returns:
            bool: 是否删除成功
        """
        selected_items = self.selectedItems()
        if not selected_items:
            return False
            
        # 获取选中项的ID列表
        ids_to_delete = [item.record_id for item in selected_items]
        
        # 删除数据库记录
        if self.history_manager.batch_delete(ids_to_delete):
            # 删除列表项
            for item in selected_items:
                self.takeItem(self.row(item))
                self.item_deleted.emit(item.record_id)
            return True
        return False
        
    def contextMenuEvent(self, event: QContextMenuEvent):
        """右键菜单事件处理
        
        Args:
            event: 上下文菜单事件
        """
        menu = QMenu(self)
        
        # 添加删除操作
        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(self._on_delete_action)
        
        # 添加复制URL操作
        copy_url_action = menu.addAction("复制URL")
        copy_url_action.triggered.connect(self._on_copy_url_action)
        
        # 显示菜单
        menu.exec_(event.globalPos())
        
    def _on_delete_action(self):
        """删除操作处理"""
        selected_items = self.selectedItems()
        if not selected_items:
            return
            
        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(selected_items)} 条记录吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.delete_selected()
            
    def _on_copy_url_action(self):
        """复制URL操作处理"""
        selected_items = self.selectedItems()
        if not selected_items:
            return
            
        # 获取第一个选中项的URL
        url = selected_items[0].url
        
        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(url) 