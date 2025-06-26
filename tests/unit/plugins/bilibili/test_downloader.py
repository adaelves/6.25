"""B站视频下载器测试模块。

该模块包含对BilibiliDownloader类的单元测试。
"""

import os
import json
import time
import pytest
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

from src.plugins.bilibili.downloader import BilibiliDownloader
from .mock_utils import MockResponse, create_video_response

class TestBilibiliDownloader:
    """B站视频下载器测试类。"""
    
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
        
        # 设置较短的超时时间用于测试
        self.original_timeout = self.downloader.timeout
        self.downloader.timeout = 5
        
        # Mock视频信息
        self.mock_video_info = {
            "bvid": "BV1xx411c7mD",
            "cid": "12345678",
            "title": "测试视频",
            "duration": 180,
            "owner": {"name": "测试UP主"},
            "is_vip_only": False,
            "is_area_limited": False
        }
        
        # Mock视频流信息
        self.mock_streams = [
            {
                "quality": 80,
                "base_url": "http://test.com/video_1080p.m4s",
                "segments": [
                    {"base_url": "http://test.com/seg1.m4s"},
                    {"base_url": "http://test.com/seg2.m4s"}
                ]
            },
            {
                "quality": 64,
                "base_url": "http://test.com/video_720p.m4s",
                "segments": [
                    {"base_url": "http://test.com/seg1_720p.m4s"},
                    {"base_url": "http://test.com/seg2_720p.m4s"}
                ]
            }
        ]
        
        yield
        
        # 恢复原始超时设置
        self.downloader.timeout = self.original_timeout
        
        # 清理测试文件
        if self.test_save_path.exists():
            try:
                self.test_save_path.unlink()
            except PermissionError:
                # Windows下可能需要等待文件释放
                time.sleep(0.1)
                self.test_save_path.unlink()
                
        # 清理临时文件
        for temp_file in self.temp_dir.glob("*.tmp"):
            try:
                temp_file.unlink()
            except (PermissionError, FileNotFoundError):
                pass

    @pytest.mark.timeout(30)  # 设置测试超时时间
    def test_download_success(self, mocker):
        """测试正常下载流程。"""
        # Mock提取器
        mock_extract = mocker.patch.object(
            self.downloader.extractor,
            "extract_info",
            return_value=self.mock_video_info
        )
        
        # Mock视频流获取
        mocker.patch.object(
            self.downloader,
            "_get_video_streams",
            return_value=self.mock_streams
        )
        
        # Mock分段下载，添加进度回调
        def mock_download_segment(*args, **kwargs):
            if "progress_callback" in kwargs:
                for i in range(0, 101, 10):
                    kwargs["progress_callback"](i)
                    time.sleep(0.01)  # 模拟下载进度
            return True
            
        mocker.patch.object(
            self.downloader,
            "_download_segment",
            side_effect=mock_download_segment
        )
        
        # Mock合并
        mocker.patch.object(
            self.downloader,
            "_merge_segments",
            return_value=True
        )
        
        # Mock弹幕下载
        mocker.patch(
            "src.plugins.bilibili.downloader.download_danmaku",
            return_value=True
        )
        
        # 执行下载
        result = self.downloader.download(self.test_url, self.test_save_path)
        
        assert result is True, "下载应该成功"
        mock_extract.assert_called_once_with(self.test_url)
        
    @pytest.mark.timeout(10)
    def test_download_vip_only(self, mocker):
        """测试大会员专享视频。"""
        # 设置为大会员视频
        self.mock_video_info["is_vip_only"] = True
        
        mocker.patch.object(
            self.downloader.extractor,
            "extract_info",
            return_value=self.mock_video_info
        )
        
        # 未登录状态
        self.downloader.extractor.sessdata = None
        
        result = self.downloader.download(self.test_url, self.test_save_path)
        assert result is False, "未登录时下载大会员视频应该失败"
        
        # 已登录状态
        self.downloader.extractor.sessdata = "valid_sessdata"
        mocker.patch.object(
            self.downloader,
            "_get_video_streams",
            return_value=self.mock_streams
        )
        mocker.patch.object(
            self.downloader,
            "_download_segment",
            return_value=True
        )
        mocker.patch.object(
            self.downloader,
            "_merge_segments",
            return_value=True
        )
        
        result = self.downloader.download(self.test_url, self.test_save_path)
        assert result is True, "登录后下载大会员视频应该成功"
        
    def test_download_area_limited(self, mocker):
        """测试地区限制视频。"""
        # 设置地区限制
        self.mock_video_info["is_area_limited"] = True
        
        mocker.patch.object(
            self.downloader.extractor,
            "extract_info",
            return_value=self.mock_video_info
        )
        
        result = self.downloader.download(self.test_url, self.test_save_path)
        assert result is False, "下载地区限制视频应该失败"
        
    def test_invalid_url(self):
        """测试无效URL。"""
        result = self.downloader.download("invalid_url", self.test_save_path)
        assert result is False, "下载无效URL应该失败"
        
    def test_download_segment_retry(self, mocker):
        """测试分段下载重试机制。"""
        # Mock网络请求
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = [
            MockResponse(status_code=500),  # 首次失败
            MockResponse(status_code=200, content=b"test_data")  # 重试成功
        ]
        
        # 执行下载
        segment_path = self.temp_dir / "test_segment.m4s"
        result = self.downloader._download_segment(
            "http://test.com/segment.m4s",
            segment_path
        )
        
        assert result is True, "分段下载重试应该成功"
        assert segment_path.exists(), "应该生成分段文件"
        assert mock_get.call_count == 2, "应该尝试两次请求"
        
    def test_merge_segments_failure(self, mocker):
        """测试合并失败处理。"""
        # Mock FFmpeg执行失败
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        
        segment_files = [
            self.temp_dir / "seg1.m4s",
            self.temp_dir / "seg2.m4s"
        ]
        
        # 创建测试分段文件
        for file in segment_files:
            file.write_bytes(b"test_data")
            
        result = self.downloader._merge_segments(segment_files, self.test_save_path)
        assert result is False, "合并失败时应该返回False"
        
    def test_quality_selection(self):
        """测试清晰度选择。"""
        # 空流列表
        with pytest.raises(RuntimeError):
            self.downloader._select_best_quality([])
            
        # 正常选择
        test_streams = [
            {"quality": 80, "base_url": "http://test.com/1080p.m4s"},
            {"quality": 64, "base_url": "http://test.com/720p.m4s"}
        ]
        
        with patch.object(
            self.downloader,
            "_check_stream_availability",
            return_value=True
        ):
            stream = self.downloader._select_best_quality(test_streams)
            assert stream["quality"] == 80, "应该选择最高清晰度"
            
    @pytest.mark.timeout(10)
    @pytest.mark.benchmark
    def test_download_performance(self, benchmark, mocker):
        """测试下载性能。"""
        # Mock所有外部调用
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
        
        # Mock下载过程，使用较短的延迟
        def mock_download(*args, **kwargs):
            time.sleep(0.01)  # 使用固定的短延迟
            return True
            
        mocker.patch.object(
            self.downloader,
            "_download_segment",
            side_effect=mock_download
        )
        mocker.patch.object(
            self.downloader,
            "_merge_segments",
            return_value=True
        )
        
        def run_benchmark():
            return self.downloader.download(self.test_url, self.test_save_path)
            
        result = benchmark(run_benchmark)
        assert result is True, "基准测试应该成功"
        
    def test_download_with_progress(self, mocker):
        """测试带进度回调的下载。"""
        # Mock提取器
        mocker.patch.object(
            self.downloader.extractor,
            "extract_info",
            return_value=self.mock_video_info
        )
        
        # Mock视频流获取
        mocker.patch.object(
            self.downloader,
            "_get_video_streams",
            return_value=self.mock_streams
        )
        
        # Mock分段大小
        mocker.patch.object(
            self.downloader,
            "_get_segment_size",
            return_value=1024 * 1024  # 1MB
        )
        
        # Mock分段下载
        mocker.patch.object(
            self.downloader,
            "_download_segment",
            return_value=True
        )
        
        # Mock合并
        mocker.patch.object(
            self.downloader,
            "_merge_segments",
            return_value=True
        )
        
        # 创建进度回调
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
        assert all(0 <= p <= 1 for p in progress_values), "进度值应该在0~1之间"
        assert progress_values[-1] == 1.0, "最终进度应该是1.0"
        
    def test_progress_callback_thread_safety(self, mocker):
        """测试进度回调的线程安全性。"""
        # Mock视频信息和流
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
        
        # Mock下载相关函数
        mocker.patch.object(
            self.downloader,
            "_get_segment_size",
            return_value=1024
        )
        mocker.patch.object(
            self.downloader,
            "_download_segment",
            return_value=True
        )
        mocker.patch.object(
            self.downloader,
            "_merge_segments",
            return_value=True
        )
        
        # 记录回调执行的线程
        callback_threads = set()
        def progress_callback(progress: float):
            callback_threads.add(threading.current_thread())
            
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            progress_callback
        )
        
        assert result is True, "下载应该成功"
        assert len(callback_threads) == 1, "回调应该在同一个线程中执行"
        assert self.downloader._main_thread in callback_threads, "回调应该在主线程中执行"
        
    def test_progress_callback_error_handling(self, mocker):
        """测试进度回调的错误处理。"""
        # Mock基本功能
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
            "_get_segment_size",
            return_value=1024
        )
        mocker.patch.object(
            self.downloader,
            "_download_segment",
            return_value=True
        )
        mocker.patch.object(
            self.downloader,
            "_merge_segments",
            return_value=True
        )
        
        # 创建会抛出异常的回调
        def error_callback(progress: float):
            raise Exception("回调错误")
            
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            error_callback
        )
        
        assert result is True, "回调错误不应该影响下载结果"
        
    def test_progress_value_bounds(self, mocker):
        """测试进度值的边界。"""
        # Mock基本功能
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
        
        # Mock分段大小返回负值
        mocker.patch.object(
            self.downloader,
            "_get_segment_size",
            side_effect=[-1024, 2048]  # 一个负值和一个正值
        )
        
        mocker.patch.object(
            self.downloader,
            "_download_segment",
            return_value=True
        )
        mocker.patch.object(
            self.downloader,
            "_merge_segments",
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
        assert all(0 <= p <= 1 for p in progress_values), "进度值应该被限制在0~1之间"
        
    @pytest.mark.benchmark
    def test_download_performance_with_callback(self, benchmark, mocker):
        """测试带回调的下载性能。"""
        # Mock所有外部调用
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
            "_get_segment_size",
            return_value=1024
        )
        mocker.patch.object(
            self.downloader,
            "_download_segment",
            return_value=True
        )
        mocker.patch.object(
            self.downloader,
            "_merge_segments",
            return_value=True
        )
        
        progress_values = []
        def progress_callback(progress: float):
            progress_values.append(progress)
            time.sleep(0.001)  # 模拟耗时操作
            
        def run_benchmark():
            return self.downloader.download(
                self.test_url,
                self.test_save_path,
                progress_callback
            )
            
        result = benchmark(run_benchmark)
        assert result is True, "基准测试应该成功" 