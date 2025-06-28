"""状态管理器测试模块。

测试GUI状态管理器的各项功能。
"""

import unittest
import threading
import time
from PySide6.QtWidgets import QApplication, QPushButton, QProgressBar, QLineEdit
from PySide6.QtCore import Qt
from src.gui.state_manager import StateManager, DownloadState

class TestStateManager(unittest.TestCase):
    """状态管理器测试类。"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化。"""
        # 创建QApplication实例
        cls.app = QApplication([])
        
    def setUp(self):
        """每个测试用例初始化。"""
        self.state_manager = StateManager()
        
        # 创建测试用的UI组件
        self.download_btn = QPushButton("下载")
        self.cancel_btn = QPushButton("取消")
        self.pause_btn = QPushButton("暂停")
        self.progress_bar = QProgressBar()
        self.url_input = QLineEdit()
        
        # 关联组件
        self.state_manager.link_widget(self.download_btn, "download_btn")
        self.state_manager.link_widget(self.cancel_btn, "cancel_btn")
        self.state_manager.link_widget(self.pause_btn, "pause_btn")
        self.state_manager.link_widget(self.progress_bar, "progress_bar")
        self.state_manager.link_widget(self.url_input, "url_input")
        
        # 记录信号触发
        self.state_changes = []
        self.progress_updates = []
        self.errors = []
        
        # 连接信号
        self.state_manager.state_changed.connect(self._on_state_changed)
        self.state_manager.progress_updated.connect(self._on_progress_updated)
        self.state_manager.error_occurred.connect(self._on_error)
        
        # 处理事件循环
        QApplication.processEvents()
        
    def _on_state_changed(self, old_state, new_state):
        """状态变更回调。"""
        self.state_changes.append((old_state, new_state))
        
    def _on_progress_updated(self, progress, message):
        """进度更新回调。"""
        self.progress_updates.append((progress, message))
        
    def _on_error(self, error):
        """错误回调。"""
        self.errors.append(error)
        
    def test_initial_state(self):
        """测试初始状态。"""
        self.assertEqual(self.state_manager.get_state(), DownloadState.STOPPED)
        self.assertTrue(self.download_btn.isEnabled())
        self.assertFalse(self.cancel_btn.isEnabled())
        self.assertFalse(self.pause_btn.isEnabled())
        self.assertFalse(self.progress_bar.isEnabled())
        self.assertTrue(self.url_input.isEnabled())
        
    def test_state_transition(self):
        """测试状态转换。"""
        # STOPPED -> RUNNING
        self.state_manager.set_state(DownloadState.RUNNING)
        QApplication.processEvents()
        
        self.assertEqual(self.state_manager.get_state(), DownloadState.RUNNING)
        self.assertEqual(len(self.state_changes), 1)
        self.assertEqual(self.state_changes[0], (DownloadState.STOPPED, DownloadState.RUNNING))
        
        # 检查UI状态
        self.assertFalse(self.download_btn.isEnabled())
        self.assertTrue(self.cancel_btn.isEnabled())
        self.assertTrue(self.pause_btn.isEnabled())
        self.assertTrue(self.progress_bar.isEnabled())
        self.assertFalse(self.url_input.isEnabled())
        
        # RUNNING -> PAUSED
        self.state_manager.set_state(DownloadState.PAUSED)
        QApplication.processEvents()
        
        self.assertEqual(self.state_manager.get_state(), DownloadState.PAUSED)
        self.assertEqual(len(self.state_changes), 2)
        self.assertEqual(self.state_changes[1], (DownloadState.RUNNING, DownloadState.PAUSED))
        
        # 检查UI状态
        self.assertTrue(self.download_btn.isEnabled())
        self.assertTrue(self.cancel_btn.isEnabled())
        self.assertFalse(self.pause_btn.isEnabled())
        self.assertFalse(self.progress_bar.isEnabled())
        self.assertFalse(self.url_input.isEnabled())
        
    def test_progress_update(self):
        """测试进度更新。"""
        self.state_manager.update_progress(0.5, "下载中...")
        QApplication.processEvents()
        
        self.assertEqual(len(self.progress_updates), 1)
        self.assertEqual(self.progress_updates[0], (0.5, "下载中..."))
        
    def test_error_handling(self):
        """测试错误处理。"""
        error_msg = "网络连接失败"
        self.state_manager.report_error(error_msg)
        QApplication.processEvents()
        
        # 检查状态变更
        self.assertEqual(self.state_manager.get_state(), DownloadState.ERROR)
        self.assertEqual(len(self.errors), 1)
        self.assertEqual(self.errors[0], error_msg)
        
        # 检查UI状态
        self.assertTrue(self.download_btn.isEnabled())
        self.assertEqual(self.download_btn.property("text"), "重试")
        self.assertFalse(self.cancel_btn.isEnabled())
        self.assertFalse(self.pause_btn.isEnabled())
        self.assertFalse(self.progress_bar.isEnabled())
        self.assertTrue(self.url_input.isEnabled())
        
    def test_thread_safety(self):
        """测试线程安全性。"""
        def state_changer():
            for state in [DownloadState.RUNNING, DownloadState.PAUSED, DownloadState.STOPPED]:
                self.state_manager.set_state(state)
                time.sleep(0.1)  # 添加延迟确保信号能被处理
                
        def progress_updater():
            for i in range(5):
                self.state_manager.update_progress(i/4, f"进度 {i}")
                time.sleep(0.1)  # 添加延迟确保信号能被处理
                
        # 创建线程
        threads = [
            threading.Thread(target=state_changer),
            threading.Thread(target=progress_updater)
        ]
        
        # 启动线程
        for t in threads:
            t.start()
            
        # 等待线程完成
        for t in threads:
            t.join()
            
        # 处理所有待处理的事件
        QApplication.processEvents()
            
        # 验证结果
        self.assertGreater(len(self.state_changes), 0)
        self.assertGreater(len(self.progress_updates), 0)
        
    def test_widget_unlink(self):
        """测试取消关联组件。"""
        self.state_manager.unlink_widget(self.download_btn)
        self.state_manager.set_state(DownloadState.RUNNING)
        QApplication.processEvents()
        
        # download_btn不应该被更新
        self.assertTrue(self.download_btn.isEnabled())
        self.assertEqual(self.download_btn.property("text"), "下载")
        
    def tearDown(self):
        """测试用例清理。"""
        # 清理组件
        self.download_btn.deleteLater()
        self.cancel_btn.deleteLater()
        self.pause_btn.deleteLater()
        self.progress_bar.deleteLater()
        self.url_input.deleteLater()
        QApplication.processEvents()
        
    @classmethod
    def tearDownClass(cls):
        """测试类清理。"""
        cls.app.quit()

if __name__ == '__main__':
    unittest.main() 