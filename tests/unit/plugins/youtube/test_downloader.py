"""YouTube下载器测试模块。"""

import logging
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, ANY
from src.plugins.youtube.downloader import YouTubeDownloader
from src.core.exceptions import DownloadError

class TestYouTubeDownloader:
    """YouTube下载器测试类。"""
    
    @pytest.fixture
    def downloader(self, tmp_path):
        """创建下载器实例。"""
        return YouTubeDownloader(save_dir=str(tmp_path))
        
    @pytest.fixture
    def mock_ydl(self):
        """Mock yt-dlp下载器。"""
        with patch('yt_dlp.YoutubeDL') as mock:
            yield mock
            
    def test_format_selector(self, downloader):
        """测试格式选择器。"""
        # 测试默认设置
        assert downloader._get_format_selector() == 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
        
        # 测试自定义最大高度
        downloader.max_height = 720
        assert downloader._get_format_selector() == 'bestvideo[height<=720]+bestaudio/best[height<=720]'
        
        # 测试偏好质量
        downloader.prefer_quality = '4K'
        downloader.max_height = 2160
        assert downloader._get_format_selector() == 'bestvideo[height<=2160]+bestaudio/best[height<=2160]'
        
    def test_download_success(self, downloader, mock_ydl, tmp_path):
        """测试成功下载。"""
        url = "https://www.youtube.com/watch?v=abc123"
        save_path = tmp_path / "test.mp4"
        
        # Mock视频信息
        mock_info = {
            'title': 'Test Video',
            'duration': 120,
            'is_short': False
        }
        
        with patch.object(downloader.extractor, 'extract_info', return_value=mock_info):
            # 设置mock
            mock_instance = Mock()
            mock_ydl.return_value.__enter__.return_value = mock_instance
            
            # 执行下载
            result = downloader.download(url, save_path)
            
            # 验证结果
            assert result is True
            mock_instance.download.assert_called_once_with([url])
            
            # 验证下载选项
            mock_ydl.assert_called_once_with({
                'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                'outtmpl': str(save_path),
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'noplaylist': True,
                'progress_hooks': [downloader._progress_hook],
                'continuedl': True,
                'noresizebuffer': True
            })
        
    def test_download_with_proxy(self, mock_ydl, tmp_path):
        """测试使用代理下载。"""
        url = "https://www.youtube.com/watch?v=abc123"
        proxy = "http://127.0.0.1:7890"
        
        # 创建带代理的下载器
        downloader = YouTubeDownloader(save_dir=str(tmp_path), proxy=proxy)
        
        # Mock视频信息
        mock_info = {'title': 'Test Video'}
        with patch.object(downloader.extractor, 'extract_info', return_value=mock_info):
            # 执行下载
            result = downloader.download(url)
            
            # 验证代理设置
            mock_ydl.assert_called_once()
            call_args = mock_ydl.call_args[0][0]
            assert call_args['proxy'] == proxy
        
    def test_download_error(self, downloader, mock_ydl, tmp_path):
        """测试下载错误。"""
        url = "https://www.youtube.com/watch?v=abc123"
        save_path = tmp_path / "test.mp4"
        
        # 设置mock抛出错误
        mock_instance = Mock()
        mock_instance.download.side_effect = Exception("Download failed")
        mock_ydl.return_value.__enter__.return_value = mock_instance
        
        # 验证是否抛出预期的异常
        with pytest.raises(DownloadError):
            downloader.download(url, save_path)
            
    def test_progress_hook(self, downloader, caplog):
        """测试进度回调。"""
        # 创建进度回调
        progress_updates = []
        def progress_callback(progress: float, status: str):
            progress_updates.append((progress, status))
            
        downloader.progress_callback = progress_callback
        
        # 测试下载中的状态
        progress_info = {
            'status': 'downloading',
            'total_bytes': 1000000,
            'downloaded_bytes': 500000,
            'speed': 1024 * 1024,  # 1MB/s
            'eta': 10
        }
        
        with caplog.at_level(logging.DEBUG):
            downloader._progress_hook(progress_info)
            assert "下载进度: 50.0%" in caplog.text
            assert "速度: 1.0MB/s" in caplog.text
            assert "剩余时间: 10秒" in caplog.text
            
            # 验证进度回调
            assert len(progress_updates) == 1
            progress, status = progress_updates[0]
            assert progress == 0.5
            assert "50.0%" in status
            assert "1.0MB/s" in status
            
        # 测试完成状态
        caplog.clear()
        progress_updates.clear()
        
        with caplog.at_level(logging.INFO):
            downloader._progress_hook({'status': 'finished'})
            assert "下载完成" in caplog.text
            
            # 验证进度回调
            assert len(progress_updates) == 1
            progress, status = progress_updates[0]
            assert progress == 1.0
            assert "下载完成" in status
            
    def test_get_video_info(self, downloader):
        """测试获取视频信息。"""
        url = "https://www.youtube.com/watch?v=abc123"
        mock_info = {
            'title': 'Test Video',
            'duration': 120,
            'is_short': False
        }
        
        with patch.object(downloader.extractor, 'extract_info', return_value=mock_info):
            info = downloader.get_video_info(url)
            assert info == mock_info
            
    def test_get_video_info_error(self, downloader):
        """测试获取视频信息错误。"""
        url = "invalid_url"
        
        with patch.object(downloader.extractor, 'extract_info', side_effect=Exception("Error")):
            with pytest.raises(DownloadError):
                downloader.get_video_info(url)
                
    def test_download_without_save_path(self, downloader, mock_ydl):
        """测试不指定保存路径的下载。"""
        url = "https://www.youtube.com/watch?v=abc123"
        
        # Mock视频信息
        mock_info = {
            'title': 'Test Video',
            'duration': 120,
            'is_short': False
        }
        
        with patch.object(downloader.extractor, 'extract_info', return_value=mock_info):
            # 设置mock
            mock_instance = Mock()
            mock_ydl.return_value.__enter__.return_value = mock_instance
            
            # 执行下载
            result = downloader.download(url)
            
            # 验证结果
            assert result is True
            mock_instance.download.assert_called_once_with([url])
            
            # 验证使用了默认保存路径
            call_args = mock_ydl.call_args[0][0]
            expected_path = str(downloader.save_dir / "Test Video.mp4")
            assert call_args['outtmpl'] == expected_path
            
    def test_download_resume(self, downloader, mock_ydl, tmp_path):
        """测试断点续传功能。"""
        url = "https://www.youtube.com/watch?v=abc123"
        save_path = tmp_path / "test.mp4"
        temp_path = save_path.with_suffix(save_path.suffix + '.part')
        
        # 创建临时文件
        temp_path.write_bytes(b'0' * 1024)  # 写入1KB数据
        
        # Mock视频信息
        mock_info = {
            'title': 'Test Video',
            'duration': 120,
            'is_short': False
        }
        
        with patch.object(downloader.extractor, 'extract_info', return_value=mock_info):
            # 设置mock
            mock_instance = Mock()
            mock_ydl.return_value.__enter__.return_value = mock_instance
            
            # 执行下载
            result = downloader.download(url, save_path)
            
            # 验证结果
            assert result is True
            mock_instance.download.assert_called_once_with([url])
            
            # 验证下载选项包含续传参数
            mock_ydl.assert_called_once()
            call_args = mock_ydl.call_args[0][0]
            assert call_args['resume'] is True
            assert call_args['start_byte'] == 1024
            
    def test_progress_hook_with_resume(self, downloader, caplog):
        """测试断点续传的进度回调。"""
        # 创建进度回调
        progress_updates = []
        def progress_callback(progress: float, status: str):
            progress_updates.append((progress, status))
            
        downloader.progress_callback = progress_callback
        
        # 测试续传的进度信息
        progress_info = {
            'status': 'downloading',
            'total_bytes': 1000000,
            'downloaded_bytes': 500000,
            'resumed_from': 200000,  # 已下载200KB
            'speed': 1024 * 1024,  # 1MB/s
            'eta': 10
        }
        
        with caplog.at_level(logging.DEBUG):
            downloader._progress_hook(progress_info)
            
            # 验证进度计算包含了已下载部分
            total_downloaded = progress_info['downloaded_bytes'] + progress_info['resumed_from']
            total_size = progress_info['total_bytes'] + progress_info['resumed_from']
            expected_progress = (total_downloaded / total_size) * 100
            
            assert f"下载进度: {expected_progress:.1f}%" in caplog.text
            assert "速度: 1.0MB/s" in caplog.text
            assert "剩余时间: 10秒" in caplog.text
            
            # 验证进度回调
            assert len(progress_updates) == 1
            progress, status = progress_updates[0]
            assert progress == expected_progress / 100
            assert f"{expected_progress:.1f}%" in status 