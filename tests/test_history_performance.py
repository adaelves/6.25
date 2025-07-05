"""历史记录性能测试模块"""

import unittest
import tempfile
import os
import time
from typing import List, Tuple
from datetime import datetime, timedelta

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

from core.history import HistoryManager
from ui.widgets.history_list import HistoryList

class TestHistoryPerformance(unittest.TestCase):
    """历史记录性能测试类"""
    
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
        
        # 生成大量测试数据
        self.generate_test_data(10000)  # 生成1万条记录
        
    def tearDown(self):
        """测试后清理"""
        self.history_manager.close()
        os.remove(self.db_path)
        os.rmdir(self.temp_dir)
        
    def generate_test_data(self, count: int):
        """生成测试数据
        
        Args:
            count: 记录数量
        """
        base_date = datetime.now()
        for i in range(count):
            url = f'https://example.com/video{i}.mp4'
            title = f'测试视频 {i}'
            date = (base_date - timedelta(days=i)).strftime('%Y-%m-%d')
            self.history_manager.add_record(url, title, date)
            
    def test_page_loading_performance(self):
        """测试分页加载性能"""
        page_sizes = [10, 50, 100]
        max_load_time = 0.1  # 100ms
        
        for page_size in page_sizes:
            # 测试首页加载
            start_time = time.time()
            records = self.history_manager.get_page(1, page_size)
            load_time = time.time() - start_time
            
            # 验证加载时间
            self.assertLess(load_time, max_load_time)
            
            # 验证记录数量
            self.assertEqual(len(records), page_size)
            
    def test_scroll_performance(self):
        """测试滚动加载性能"""
        page_size = 50
        total_pages = 5
        max_load_time = 0.5  # 500ms
        
        # 模拟连续滚动加载
        start_time = time.time()
        for page in range(1, total_pages + 1):
            records = self.history_manager.get_page(page, page_size)
            self.history_list.add_items(records)
            
        load_time = time.time() - start_time
        
        # 验证总加载时间
        self.assertLess(load_time, max_load_time)
        
        # 验证加载的记录总数
        self.assertEqual(self.history_list.count(), page_size * total_pages)
        
    def test_search_performance(self):
        """测试搜索性能"""
        search_terms = ['测试', 'video', '2024']
        max_search_time = 0.2  # 200ms
        
        for term in search_terms:
            start_time = time.time()
            results = self.history_manager.search_records(term)
            search_time = time.time() - start_time
            
            # 验证搜索时间
            self.assertLess(search_time, max_search_time)
            
    def test_filter_performance(self):
        """测试过滤性能"""
        # 测试日期范围过滤
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
        
        start_time = time.time()
        filtered_records = self.history_manager.filter_by_date_range(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        filter_time = time.time() - start_time
        
        # 验证过滤时间
        self.assertLess(filter_time, 0.2)  # 200ms
        
    def test_memory_usage(self):
        """测试内存使用"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 加载1000条记录
        records = self.history_manager.get_page(1, 1000)
        self.history_list.add_items(records)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # 验证内存增长不超过50MB
        self.assertLess(memory_increase, 50)

if __name__ == '__main__':
    unittest.main() 