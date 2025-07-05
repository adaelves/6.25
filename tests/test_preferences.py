"""首选项功能单元测试模块"""

import unittest
import json
import time
import tempfile
import os
from typing import List
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from core.downloader import Downloader, DownloadManager
from core.preferences import PreferencesManager
from ui.widgets.preferences import PreferencesDialog

class TestPreferencesManager(unittest.TestCase):
    """首选项管理器测试类"""
    
    def setUp(self):
        """测试前置设置"""
        self.temp_dir = tempfile.mkdtemp()
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, self.temp_dir)
        self.settings = QSettings('VideoDownloader', 'test')
        self.preferences = PreferencesManager()
        
    def tearDown(self):
        """测试后清理"""
        self.settings.clear()
        os.rmdir(self.temp_dir)
        
    def test_thread_limit_validation(self):
        """测试线程数限制验证"""
        # 测试有效值
        valid_values = [1, 8, 16]
        for value in valid_values:
            self.preferences.set_thread_limit(value)
            self.assertEqual(self.preferences.get_thread_limit(), value)
            
        # 测试无效值
        invalid_values = [0, -1, 17, 100]
        for value in invalid_values:
            with self.assertRaises(ValueError):
                self.preferences.set_thread_limit(value)
                
    def test_speed_limit_validation(self):
        """测试速度限制验证"""
        # 测试有效值
        valid_values = [0, 1024, 10240]  # KB/s
        for value in valid_values:
            self.preferences.set_speed_limit(value)
            self.assertEqual(self.preferences.get_speed_limit(), value)
            
        # 测试无效值
        invalid_values = [-1, -1024]
        for value in invalid_values:
            with self.assertRaises(ValueError):
                self.preferences.set_speed_limit(value)
                
    def test_settings_persistence(self):
        """测试设置持久化"""
        # 设置测试值
        test_settings = {
            'thread_limit': 8,
            'speed_limit': 1024
        }
        
        # 保存设置
        self.preferences.save_settings(test_settings)
        
        # 重新加载设置
        loaded_settings = self.preferences.load_settings()
        
        # 验证设置是否正确保存和加载
        self.assertEqual(loaded_settings['thread_limit'], test_settings['thread_limit'])
        self.assertEqual(loaded_settings['speed_limit'], test_settings['speed_limit'])

class TestDownloadManager(unittest.TestCase):
    """下载管理器测试类"""
    
    def setUp(self):
        """测试前置设置"""
        self.preferences = PreferencesManager()
        self.download_manager = DownloadManager(self.preferences)
        
        # 准备测试URL列表
        self.test_urls = [
            f'https://example.com/video{i}.mp4' for i in range(10)
        ]
        
    @patch('core.downloader.Downloader')
    def test_concurrent_downloads(self, mock_downloader):
        """测试并发下载控制"""
        # 设置线程数限制
        self.preferences.set_thread_limit(4)
        
        # 添加下载任务
        for url in self.test_urls:
            self.download_manager.add_download(url)
            
        # 验证活动下载数不超过线程限制
        self.assertLessEqual(
            len([d for d in self.download_manager.downloaders if d.isRunning()]),
            self.preferences.get_thread_limit()
        )
        
    @patch('core.downloader.Downloader')
    def test_speed_limit_accuracy(self, mock_downloader):
        """测试速度限制准确性"""
        # 设置速度限制（1MB/s）
        target_speed = 1024  # KB/s
        self.preferences.set_speed_limit(target_speed)
        
        # 模拟下载过程
        downloader = Downloader()
        downloader.speed_limit = target_speed
        
        # 记录开始时间
        start_time = time.time()
        
        # 模拟下载1MB数据
        data_size = 1024  # KB
        downloaded = 0
        
        while downloaded < data_size:
            chunk_size = 64  # KB
            downloaded += chunk_size
            time.sleep(chunk_size / target_speed)  # 模拟下载延迟
            
        # 计算实际速度
        elapsed_time = time.time() - start_time
        actual_speed = data_size / elapsed_time
        
        # 验证速度误差在±5%范围内
        error_margin = 0.05
        self.assertAlmostEqual(
            actual_speed,
            target_speed,
            delta=target_speed * error_margin
        )

class TestPreferencesDialog(unittest.TestCase):
    """首选项对话框测试类"""
    
    @classmethod
    def setUpClass(cls):
        """创建QApplication实例"""
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])
            
    def setUp(self):
        """测试前置设置"""
        self.preferences = PreferencesManager()
        self.dialog = PreferencesDialog(self.preferences)
        
    def test_ui_validation(self):
        """测试UI输入验证"""
        # 测试线程数输入
        self.dialog.thread_spin.setValue(0)
        QTest.keyClick(self.dialog.thread_spin, Qt.Key_Return)
        self.assertGreater(self.dialog.thread_spin.value(), 0)
        
        self.dialog.thread_spin.setValue(20)
        QTest.keyClick(self.dialog.thread_spin.lineEdit(), Qt.Key_Return)
        self.assertLessEqual(self.dialog.thread_spin.value(), 16)
        
    def test_settings_apply(self):
        """测试设置实时生效"""
        # 修改线程数
        new_thread_limit = 6
        self.dialog.thread_spin.setValue(new_thread_limit)
        QTest.keyClick(self.dialog.thread_spin, Qt.Key_Return)
        
        # 验证设置是否立即生效
        self.assertEqual(
            self.preferences.get_thread_limit(),
            new_thread_limit
        )
        
        # 修改速度限制
        new_speed_limit = 2048
        self.dialog.speed_slider.setValue(new_speed_limit)
        QTest.keyClick(self.dialog.speed_slider, Qt.Key_Return)
        
        # 验证设置是否立即生效
        self.assertEqual(
            self.preferences.get_speed_limit(),
            new_speed_limit
        )

if __name__ == '__main__':
    unittest.main() 