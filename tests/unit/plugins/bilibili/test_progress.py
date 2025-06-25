"""B站下载进度回调测试模块。

该模块专门测试下载进度回调的功能。
"""

import time
import queue
import threading
import pytest
from pathlib import Path
from typing import List, Set
from unittest.mock import Mock, patch

from src.plugins.bilibili.downloader import BilibiliDownloader
from .mock_utils import create_video_response

class TestProgressCallback:
    """下载进度回调测试类。"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, tmp_path):
        """测试前置和后置操作。
        
        Args:
            tmp_path: pytest提供的临时目录路径
        """
        self.downloader = BilibiliDownloader()
        self.temp_dir = tmp_path
        self.test_url = "https://www.bilibili.com/video/BV1xx411c7mD"
        self.test_save_path = self.temp_dir / "test_video.mp4"
        
        # Mock视频信息
        self.mock_video_info = {
            "bvid": "BV1xx411c7mD",
            "cid": "12345678",
            "title": "测试视频",
            "duration": 180,
            "owner": {"name": "测试UP主"}
        }
        
        # Mock视频流信息
        self.mock_streams = [
            {
                "quality": 80,
                "segments": [
                    {"base_url": "http://test.com/seg1.m4s"},
                    {"base_url": "http://test.com/seg2.m4s"},
                    {"base_url": "http://test.com/seg3.m4s"}
                ]
            }
        ]
        
        yield
        
        # 清理测试文件
        if self.test_save_path.exists():
            self.test_save_path.unlink()
            
    def _setup_mocks(self, mocker):
        """设置通用的Mock对象。
        
        Args:
            mocker: pytest-mock提供的mocker
        """
        mocker.patch.object(
            self.downloader.extractor,
            "extract_info",
            return_value=self.mock_video_info
        )
        mocker.patch.object(
            self.downloader,
            "_get_video_streams",
            return_value=self.mock_streams
        )
        mocker.patch.object(
            self.downloader,
            "_merge_segments",
            return_value=True
        )
        
    def test_progress_reporting(self, mocker):
        """测试进度报告的基本功能。"""
        self._setup_mocks(mocker)
        
        # Mock分段大小为固定值
        segment_size = 1024 * 1024  # 1MB
        mocker.patch.object(
            self.downloader,
            "_get_segment_size",
            return_value=segment_size
        )
        
        # Mock下载成功
        mocker.patch.object(
            self.downloader,
            "_download_segment",
            return_value=True
        )
        
        # 记录进度值
        progress_values = []
        def progress_callback(progress: float):
            progress_values.append(progress)
            
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            progress_callback
        )
        
        assert result is True, "下载应该成功"
        assert len(progress_values) > 0, "应该有进度更新"
        assert progress_values[0] > 0, "初始进度应该大于0"
        assert 0.99 <= progress_values[-1] <= 1.0, "最终进度应该接近或等于1.0"
        assert all(0 <= p <= 1 for p in progress_values), "所有进度值应该在0~1之间"
        assert progress_values == sorted(progress_values), "进度值应该递增"
        
    def test_progress_thread_safety(self, mocker):
        """测试进度回调的线程安全性。"""
        self._setup_mocks(mocker)
        
        # 使用队列记录回调的线程ID
        callback_threads: queue.Queue = queue.Queue()
        main_thread = threading.current_thread()
        
        def progress_callback(progress: float):
            callback_threads.put(threading.current_thread())
            time.sleep(0.001)  # 模拟耗时操作
            
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            progress_callback
        )
        
        assert result is True, "下载应该成功"
        
        # 检查所有回调是否都在主线程执行
        threads = set()
        while not callback_threads.empty():
            threads.add(callback_threads.get())
            
        assert len(threads) == 1, "回调应该只在一个线程中执行"
        assert main_thread in threads, "回调应该在主线程中执行"
        
    def test_progress_value_monotonicity(self, mocker):
        """测试进度值的单调性。"""
        self._setup_mocks(mocker)
        
        # 模拟不同大小的分段
        segment_sizes = [1024, 2048, 1536]  # 递增、递减的大小
        size_iter = iter(segment_sizes)
        mocker.patch.object(
            self.downloader,
            "_get_segment_size",
            side_effect=lambda _: next(size_iter)
        )
        
        # 记录进度值
        progress_values = []
        def progress_callback(progress: float):
            progress_values.append(progress)
            
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            progress_callback
        )
        
        assert result is True, "下载应该成功"
        
        # 验证进度值的单调性
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i-1], \
                f"进度值应该单调递增: {progress_values[i-1]} -> {progress_values[i]}"
                
    def test_progress_with_errors(self, mocker):
        """测试错误情况下的进度回调。"""
        self._setup_mocks(mocker)
        
        # 模拟下载失败
        mocker.patch.object(
            self.downloader,
            "_download_segment",
            side_effect=Exception("下载失败")
        )
        
        # 记录进度值
        progress_values = []
        error_count = 0
        
        def progress_callback(progress: float):
            if progress < 0 or progress > 1:
                nonlocal error_count
                error_count += 1
            progress_values.append(progress)
            
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            progress_callback
        )
        
        assert result is False, "下载应该失败"
        assert error_count == 0, "不应该有超出范围的进度值"
        assert all(0 <= p <= 1 for p in progress_values), "进度值应该在有效范围内"
        
    def test_progress_with_zero_size(self, mocker):
        """测试文件大小为0时的进度回调。"""
        self._setup_mocks(mocker)
        
        # 模拟文件大小为0
        mocker.patch.object(
            self.downloader,
            "_get_segment_size",
            return_value=0
        )
        
        # 记录进度值
        progress_values = []
        def progress_callback(progress: float):
            progress_values.append(progress)
            
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            progress_callback
        )
        
        assert result is True, "下载应该成功"
        assert all(0 <= p <= 1 for p in progress_values), "进度值应该在有效范围内"
        
    def test_progress_callback_frequency(self, mocker):
        """测试进度回调的频率。"""
        self._setup_mocks(mocker)
        
        # 记录回调时间
        callback_times = []
        def progress_callback(progress: float):
            callback_times.append(time.time())
            
        # 执行下载
        start_time = time.time()
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            progress_callback
        )
        end_time = time.time()
        
        assert result is True, "下载应该成功"
        
        if len(callback_times) > 1:
            # 计算回调间隔
            intervals = [
                callback_times[i] - callback_times[i-1]
                for i in range(1, len(callback_times))
            ]
            avg_interval = sum(intervals) / len(intervals)
            
            # 回调间隔不应该太小（避免过于频繁）
            assert avg_interval >= 0.01, "回调间隔应该合理"
            
            # 总耗时应该合理
            total_time = end_time - start_time
            assert total_time >= len(callback_times) * 0.01, "总耗时应该合理"
            
    @pytest.mark.benchmark
    def test_progress_callback_performance(self, benchmark, mocker):
        """测试进度回调的性能影响。"""
        self._setup_mocks(mocker)
        
        # 创建一个耗时的回调函数
        def slow_callback(progress: float):
            time.sleep(0.001)  # 模拟耗时操作
            
        def run_benchmark():
            return self.downloader.download(
                self.test_url,
                self.test_save_path,
                slow_callback
            )
            
        # 执行基准测试
        result = benchmark(run_benchmark)
        assert result is True, "基准测试应该成功" 