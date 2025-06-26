"""B站视频下载取消功能测试模块。

该模块测试下载取消功能的实现。
"""

import os
import time
import threading
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import requests
from warnings import warn as ResourceWarning

from src.plugins.bilibili.downloader import BilibiliDownloader
from src.core.exceptions import DownloadCanceled
from .mock_utils import create_video_response

class TestDownloadCancel:
    """下载取消功能测试类。"""
    
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
            
    def test_immediate_cancel(self, mocker):
        """测试立即取消下载。"""
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
        
        # 创建取消事件
        cancel_event = threading.Event()
        cancel_event.set()  # 立即取消
        
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            cancel_event=cancel_event
        )
        
        assert result is False, "取消下载应该返回False"
        assert not self.test_save_path.exists(), "不应该生成输出文件"
        assert len(self.downloader._temp_files) == 0, "应该清理所有临时文件"
        
    def test_cancel_during_download(self, mocker):
        """测试下载过程中取消。"""
        # Mock网络请求
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_content.return_value = [b"chunk"] * 10
        
        mocker.patch("requests.get", return_value=mock_response)
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
        
        # 创建取消事件
        cancel_event = threading.Event()
        
        def delayed_cancel():
            time.sleep(0.1)  # 等待下载开始
            cancel_event.set()
            
        # 启动延迟取消线程
        cancel_thread = threading.Thread(target=delayed_cancel)
        cancel_thread.start()
        
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            cancel_event=cancel_event
        )
        
        cancel_thread.join()
        
        assert result is False, "取消下载应该返回False"
        assert not self.test_save_path.exists(), "不应该生成输出文件"
        assert len(self.downloader._temp_files) == 0, "应该清理所有临时文件"
        
    def test_cancel_cleanup(self, mocker):
        """测试取消时的资源清理。"""
        # 创建测试文件
        test_files = []
        for i in range(3):
            path = self.temp_dir / f"segment_{i:03d}.m4s"
            path.write_bytes(b"test")
            test_files.append(path)
            self.downloader._temp_files.add(path)
            
        # Mock网络请求
        mock_response = Mock()
        mock_response.close = Mock()
        mocker.patch("requests.get", return_value=mock_response)
        
        # 创建取消事件
        cancel_event = threading.Event()
        cancel_event.set()
        
        # 执行下载
        self.downloader.download(
            self.test_url,
            self.test_save_path,
            cancel_event=cancel_event
        )
        
        # 验证资源清理
        assert mock_response.close.called, "应该关闭网络连接"
        for file in test_files:
            assert not file.exists(), f"应该删除临时文件 {file}"
        assert len(self.downloader._temp_files) == 0, "应该清空临时文件列表"
        
    def test_cancel_with_progress(self, mocker):
        """测试带进度回调的取消。"""
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
        
        # 记录进度值
        progress_values = []
        def progress_callback(progress: float):
            progress_values.append(progress)
            
        # 创建取消事件
        cancel_event = threading.Event()
        
        def delayed_cancel():
            while len(progress_values) < 2:  # 等待至少2个进度更新
                time.sleep(0.01)
            cancel_event.set()
            
        # 启动延迟取消线程
        cancel_thread = threading.Thread(target=delayed_cancel)
        cancel_thread.start()
        
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            progress_callback=progress_callback,
            cancel_event=cancel_event
        )
        
        cancel_thread.join()
        
        assert result is False, "取消下载应该返回False"
        assert len(progress_values) >= 2, "应该有多个进度更新"
        assert all(0 <= p <= 1 for p in progress_values), "进度值应该在0~1之间"
        assert progress_values == sorted(progress_values), "进度值应该递增"
        
    @pytest.mark.parametrize("segment_count", [1, 3, 5])
    def test_cancel_with_multiple_segments(self, mocker, segment_count):
        """测试多分段下载的取消。
        
        Args:
            segment_count: 分段数量
        """
        # 创建指定数量的分段
        segments = [
            {"base_url": f"http://test.com/seg{i}.m4s"}
            for i in range(segment_count)
        ]
        self.mock_streams[0]["segments"] = segments
        
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
        
        # 记录已下载的分段
        downloaded_segments = []
        def mock_download_segment(*args, **kwargs):
            if len(downloaded_segments) < segment_count // 2:
                downloaded_segments.append(args[1])
                return True
            return False
            
        mocker.patch.object(
            self.downloader,
            "_download_segment",
            side_effect=mock_download_segment
        )
        
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path
        )
        
        assert result is False, "下载失败应该返回False"
        assert len(downloaded_segments) == segment_count // 2, "应该只下载一半分段"
        assert len(self.downloader._temp_files) == 0, "应该清理所有临时文件"
        
    def test_cancel_error_handling(self, mocker):
        """测试取消过程中的错误处理。"""
        # Mock清理失败的临时文件
        bad_path = self.temp_dir / "bad_segment.m4s"
        self.downloader._temp_files.add(bad_path)
        
        def mock_unlink():
            raise OSError("模拟删除失败")
            
        mocker.patch.object(Path, "unlink", side_effect=mock_unlink)
        
        # 创建取消事件
        cancel_event = threading.Event()
        cancel_event.set()
        
        # 执行下载
        with pytest.raises(OSError):
            self.downloader.download(
                self.test_url,
                self.test_save_path,
                cancel_event=cancel_event
            )
            
    @pytest.mark.benchmark
    def test_cancel_performance(self, benchmark, mocker):
        """测试取消操作的性能。"""
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
        
        def run_benchmark():
            cancel_event = threading.Event()
            cancel_event.set()
            return self.downloader.download(
                self.test_url,
                self.test_save_path,
                cancel_event=cancel_event
            )
            
        result = benchmark(run_benchmark)
        assert result is False, "基准测试应该返回False"
        
    def test_no_resource_leak(self, mocker):
        """测试资源泄漏。"""
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
        
        # Mock网络请求
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_content.return_value = [b"chunk"] * 5
        mock_response.close = Mock()  # 添加close方法的mock
        
        mocker.patch("requests.get", return_value=mock_response)
        
        # 创建取消事件并立即设置
        cancel_event = threading.Event()
        cancel_event.set()
        
        # 使用pytest.warns检查ResourceWarning
        with pytest.warns(ResourceWarning, match="unclosed.*"):
            self.downloader.download(
                self.test_url,
                self.test_save_path,
                cancel_event=cancel_event
            )
            
        # 验证response.close被调用
        assert mock_response.close.called, "应该调用response.close()"
        
    def test_cleanup_on_error(self, mocker):
        """测试错误情况下的资源清理。"""
        # Mock网络请求在下载过程中抛出异常
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.iter_content.side_effect = requests.RequestException("模拟网络错误")
        mock_response.close = Mock()
        
        mocker.patch("requests.get", return_value=mock_response)
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
        
        # 执行下载
        result = self.downloader.download(self.test_url, self.test_save_path)
        
        assert result is False, "下载应该失败"
        assert mock_response.close.called, "即使发生错误也应该调用response.close()"
        assert len(self.downloader._temp_files) == 0, "应该清理所有临时文件"
        
    def test_concurrent_cancellation(self, mocker):
        """测试并发下载时的取消。"""
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
        
        # 创建多个响应对象
        responses = []
        for _ in range(3):  # 模拟3个并发下载
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_response.iter_content.return_value = [b"chunk"] * 10
            mock_response.close = Mock()
            responses.append(mock_response)
            
        mock_get = mocker.patch("requests.get")
        mock_get.side_effect = responses
        
        # 创建取消事件
        cancel_event = threading.Event()
        
        def delayed_cancel():
            time.sleep(0.1)  # 等待所有下载开始
            cancel_event.set()
            
        # 启动延迟取消线程
        cancel_thread = threading.Thread(target=delayed_cancel)
        cancel_thread.start()
        
        # 执行下载
        result = self.downloader.download(
            self.test_url,
            self.test_save_path,
            cancel_event=cancel_event
        )
        
        cancel_thread.join()
        
        assert result is False, "取消下载应该返回False"
        assert all(r.close.called for r in responses), "应该关闭所有响应"
        assert len(self.downloader._temp_files) == 0, "应该清理所有临时文件" 