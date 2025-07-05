"""历史记录功能单元测试模块"""

import unittest
import sqlite3
import tempfile
import os
from datetime import datetime
from typing import List, Tuple

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

from core.history import HistoryManager
from ui.widgets.history_list import HistoryList

class TestHistoryManager(unittest.TestCase):
    """历史记录管理器测试类"""
    
    def setUp(self):
        """测试前置设置"""
        # 创建临时数据库文件
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_history.db')
        self.history_manager = HistoryManager(self.db_path)
        
        # 准备测试数据
        self.test_records = [
            ('https://example.com/1', '测试视频1', '2024-01-01'),
            ('https://example.com/2', '测试视频2', '2024-01-02'),
            ('https://example.com/3', '测试视频3', '2024-01-03')
        ]
        
    def tearDown(self):
        """测试后清理"""
        self.history_manager.close()
        os.remove(self.db_path)
        os.rmdir(self.temp_dir)
        
    def test_database_init(self):
        """测试数据库初始化"""
        # 验证表是否创建
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='downloads'")
        table_exists = cursor.fetchone() is not None
        conn.close()
        
        self.assertTrue(table_exists)
        
    def test_add_record(self):
        """测试添加记录"""
        url, title, date = self.test_records[0]
        self.history_manager.add_record(url, title, date)
        
        # 验证记录是否添加成功
        record = self.history_manager.get_record_by_url(url)
        self.assertIsNotNone(record)
        self.assertEqual(record[1], url)
        self.assertEqual(record[2], title)
        self.assertEqual(record[3], date)
        
    def test_batch_delete(self):
        """测试批量删除功能"""
        # 添加测试记录
        for url, title, date in self.test_records:
            self.history_manager.add_record(url, title, date)
            
        # 获取要删除的ID列表
        ids_to_delete = [1, 2]
        self.history_manager.batch_delete(ids_to_delete)
        
        # 验证记录是否被删除
        remaining_records = self.history_manager.get_all_records()
        self.assertEqual(len(remaining_records), 1)
        
    def test_get_recent_records(self):
        """测试获取最近记录"""
        # 添加测试记录
        for url, title, date in self.test_records:
            self.history_manager.add_record(url, title, date)
            
        # 测试限制数量
        recent_records = self.history_manager.get_recent_records(limit=2)
        self.assertEqual(len(recent_records), 2)
        
        # 验证排序是否正确（按日期降序）
        self.assertEqual(recent_records[0][3], '2024-01-03')
        self.assertEqual(recent_records[1][3], '2024-01-02')

class TestHistoryList(unittest.TestCase):
    """历史记录列表UI测试类"""
    
    @classmethod
    def setUpClass(cls):
        """创建QApplication实例"""
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])
            
    def setUp(self):
        """测试前置设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_history.db')
        self.history_manager = HistoryManager(self.db_path)
        self.history_list = HistoryList(self.history_manager)
        
        # 准备测试数据
        self.test_records = [
            ('https://example.com/1', '测试视频1', '2024-01-01'),
            ('https://example.com/2', '测试视频2', '2024-01-02'),
            ('https://example.com/3', '测试视频3', '2024-01-03')
        ]
        
    def tearDown(self):
        """测试后清理"""
        self.history_manager.close()
        os.remove(self.db_path)
        os.rmdir(self.temp_dir)
        
    def test_list_rendering(self):
        """测试列表渲染性能"""
        # 添加大量测试数据
        for i in range(1000):
            url = f'https://example.com/{i}'
            title = f'测试视频{i}'
            date = datetime.now().strftime('%Y-%m-%d')
            self.history_manager.add_record(url, title, date)
            
        # 计时加载数据
        start_time = datetime.now()
        self.history_list.load_records()
        end_time = datetime.now()
        
        # 验证加载时间是否在可接受范围内（小于1秒）
        load_time = (end_time - start_time).total_seconds()
        self.assertLess(load_time, 1.0)
        
        # 验证是否所有记录都被加载
        self.assertEqual(self.history_list.count(), 1000)
        
    def test_selection_and_deletion(self):
        """测试选择和删除功能"""
        # 添加测试记录
        for url, title, date in self.test_records:
            self.history_manager.add_record(url, title, date)
        self.history_list.load_records()
        
        # 选择前两项
        self.history_list.item(0).setSelected(True)
        self.history_list.item(1).setSelected(True)
        
        # 获取选中的项
        selected_items = self.history_list.selectedItems()
        self.assertEqual(len(selected_items), 2)
        
        # 删除选中项
        self.history_list.delete_selected()
        
        # 验证删除后的列表状态
        self.assertEqual(self.history_list.count(), 1)
        
if __name__ == '__main__':
    unittest.main() 