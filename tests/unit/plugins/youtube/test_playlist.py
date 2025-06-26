"""YouTube播放列表下载器测试模块。"""

import logging
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, ANY
import yt_dlp

from src.plugins.youtube.playlist import YouTubePlaylistDownloader
from src.core.exceptions import DownloadError

class TestYouTubePlaylistDownloader:
    """YouTube播放列表下载器测试类。"""
    
    @pytest.fixture
    def downloader(self, tmp_path):
        """创建下载器实例。"""
        return YouTubePlaylistDownloader(save_dir=str(tmp_path))
        
    @pytest.fixture
    def mock_ydl(self):
        """Mock yt-dlp下载器。"""
        with patch('yt_dlp.YoutubeDL') as mock:
            yield mock
            
    @pytest.mark.parametrize("url,expected_count", [
        ("https://youtube.com/playlist?list=PL123", 20),
        ("https://youtu.be/video123?list=XYZ456", 10),
        ("https://youtube.com/watch?v=abc&list=DEF789", 15)
    ])
    def test_playlist_parsing(self, url, expected_count, downloader, mock_ydl):
        """测试播放列表解析。"""
        # 准备mock数据
        mock_entries = [
            {'id': f'video{i}'} for i in range(expected_count)
        ]
        mock_info = {'entries': mock_entries}
        
        # 设置mock
        mock_instance = Mock()
        mock_instance.extract_info.return_value = mock_info
        mock_ydl.return_value.__enter__.return_value = mock_instance
        
        # 执行测试
        video_ids = downloader.get_video_ids(url)
        
        # 验证结果
        assert len(video_ids) == expected_count
        assert all(id.startswith('video') for id in video_ids)
        
    def test_invalid_playlist_url(self, downloader):
        """测试无效的播放列表URL。"""
        invalid_urls = [
            "https://youtube.com/watch?v=123",  # 无播放列表ID
            "https://youtu.be/123",  # 无播放列表ID
            "https://example.com/playlist?list=123"  # 非YouTube域名
        ]
        
        for url in invalid_urls:
            with pytest.raises(ValueError):
                downloader.get_video_ids(url)
                
    def test_empty_playlist(self, downloader, mock_ydl):
        """测试空播放列表。"""
        url = "https://youtube.com/playlist?list=EMPTY"
        
        # 设置mock返回空列表
        mock_instance = Mock()
        mock_instance.extract_info.return_value = {'entries': []}
        mock_ydl.return_value.__enter__.return_value = mock_instance
        
        # 验证返回空列表
        video_ids = downloader.get_video_ids(url)
        assert len(video_ids) == 0
        
    def test_playlist_download_all(self, downloader, mock_ydl, tmp_path):
        """测试播放列表完整下载。"""
        url = "https://youtube.com/playlist?list=TEST123"
        video_count = 5
        
        # 准备mock数据
        mock_entries = [
            {'id': f'video{i}'} for i in range(video_count)
        ]
        mock_info = {'entries': mock_entries}
        
        # 设置mock
        mock_instance = Mock()
        mock_instance.extract_info.return_value = mock_info
        mock_ydl.return_value.__enter__.return_value = mock_instance
        
        # Mock视频下载器
        with patch.object(downloader.video_downloader, 'download', return_value=True):
            # 执行下载
            result = downloader.download_all(url, concurrency=2)
            
            # 验证结果
            assert result is True
            assert downloader._completed_videos == video_count
            
    def test_playlist_download_with_errors(self, downloader, mock_ydl, tmp_path):
        """测试播放列表下载出错情况。"""
        url = "https://youtube.com/playlist?list=TEST123"
        video_count = 5
        
        # 准备mock数据
        mock_entries = [
            {'id': f'video{i}'} for i in range(video_count)
        ]
        mock_info = {'entries': mock_entries}
        
        # 设置mock
        mock_instance = Mock()
        mock_instance.extract_info.return_value = mock_info
        mock_ydl.return_value.__enter__.return_value = mock_instance
        
        # Mock视频下载器，一半成功一半失败
        success_count = 0
        def mock_download(url):
            nonlocal success_count
            success = success_count < video_count // 2
            success_count += 1
            if not success:
                raise DownloadError("模拟下载失败")
            return True
            
        with patch.object(downloader.video_downloader, 'download', side_effect=mock_download):
            # 执行下载
            result = downloader.download_all(url, concurrency=2)
            
            # 验证结果
            assert result is True  # 整体下载仍然完成
            assert downloader._completed_videos == video_count // 2  # 一半成功
            
    def test_progress_callback(self, downloader, mock_ydl, tmp_path):
        """测试进度回调。"""
        url = "https://youtube.com/playlist?list=TEST123"
        video_count = 5
        
        # 准备mock数据
        mock_entries = [
            {'id': f'video{i}'} for i in range(video_count)
        ]
        mock_info = {'entries': mock_entries}
        
        # 设置mock
        mock_instance = Mock()
        mock_instance.extract_info.return_value = mock_info
        mock_ydl.return_value.__enter__.return_value = mock_instance
        
        # 记录进度回调
        progress_updates = []
        def progress_callback(progress: float, status: str):
            progress_updates.append((progress, status))
            
        downloader.progress_callback = progress_callback
        
        # Mock视频下载器
        with patch.object(downloader.video_downloader, 'download', return_value=True):
            # 执行下载
            result = downloader.download_all(url, concurrency=2)
            
            # 验证进度回调
            assert len(progress_updates) == video_count  # 每个视频都有进度更新
            assert progress_updates[-1][0] == 1.0  # 最后进度为100%
            assert f"{video_count}/{video_count}" in progress_updates[-1][1]  # 最后状态显示全部完成 