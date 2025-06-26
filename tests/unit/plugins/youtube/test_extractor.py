"""YouTube视频提取器测试模块。"""

import pytest
from unittest.mock import Mock, patch
from src.plugins.youtube.extractor import YouTubeExtractor

class TestYouTubeExtractor:
    """YouTube提取器测试类。"""
    
    @pytest.fixture
    def extractor(self):
        """创建提取器实例。"""
        return YouTubeExtractor()
        
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/shorts/abc123", True),
        ("https://youtube.com/shorts/xyz789", True),
        ("https://www.youtube.com/watch?v=abc123", False),
        ("https://youtu.be/abc123", False),
        ("https://www.youtube.com/playlist?list=abc123", False),
        ("invalid_url", False)
    ])
    def test_is_shorts(self, extractor, url, expected):
        """测试Shorts链接检测。
        
        Args:
            extractor: YouTubeExtractor实例
            url: 测试URL
            expected: 期望的检测结果
        """
        assert extractor.is_shorts(url) == expected
        
    def test_extract_shorts_info(self, extractor):
        """测试提取Shorts信息。"""
        url = "https://www.youtube.com/shorts/abc123"
        
        # Mock yt-dlp提取结果
        mock_info = {
            'title': 'Test Shorts',
            'uploader': 'Test Channel',
            'formats': [{'height': 720}, {'height': 1080}],
            'view_count': 1000,
            'like_count': 100,
            'duration': 120  # 超过60秒
        }
        
        with patch('yt_dlp.YoutubeDL') as mock_ydl:
            # 设置mock
            mock_ydl.return_value.__enter__.return_value.extract_info.return_value = mock_info
            
            # 提取信息
            info = extractor.extract_info(url)
            
            # 验证结果
            assert info['is_short'] is True
            assert info['duration'] == 60  # 应该被限制在60秒
            assert info['title'] == 'Test Shorts'
            assert info['author'] == 'Test Channel'
            assert '720p' in info['quality']
            assert '1080p' in info['quality']
            
    def test_extract_normal_video_info(self, extractor):
        """测试提取普通视频信息。"""
        url = "https://www.youtube.com/watch?v=abc123"
        
        # Mock yt-dlp提取结果
        mock_info = {
            'title': 'Test Video',
            'uploader': 'Test Channel',
            'formats': [{'height': 720}, {'height': 1080}],
            'view_count': 1000,
            'like_count': 100,
            'duration': 120
        }
        
        with patch('yt_dlp.YoutubeDL') as mock_ydl:
            # 设置mock
            mock_ydl.return_value.__enter__.return_value.extract_info.return_value = mock_info
            
            # 提取信息
            info = extractor.extract_info(url)
            
            # 验证结果
            assert info['is_short'] is False
            assert info['duration'] == 120  # 不应该被限制
            assert info['title'] == 'Test Video'
            assert info['author'] == 'Test Channel'
            assert '720p' in info['quality']
            assert '1080p' in info['quality']
            
    def test_age_restricted_video(self, extractor):
        """测试年龄限制视频。"""
        url = "https://www.youtube.com/watch?v=abc123"
        
        # 第一次调用返回年龄限制信息
        mock_info_restricted = {
            'age_limit': 18,
            'title': 'Age Restricted Video'
        }
        
        # 第二次调用返回完整信息
        mock_info_full = {
            'title': 'Age Restricted Video',
            'uploader': 'Test Channel',
            'formats': [{'height': 720}],
            'view_count': 1000,
            'like_count': 100,
            'duration': 60
        }
        
        with patch('yt_dlp.YoutubeDL') as mock_ydl:
            # 设置mock按顺序返回不同的结果
            mock_instance = Mock()
            mock_instance.extract_info.side_effect = [mock_info_restricted, mock_info_full]
            mock_ydl.return_value.__enter__.return_value = mock_instance
            
            # 提取信息
            info = extractor.extract_info(url)
            
            # 验证结果
            assert info['title'] == 'Age Restricted Video'
            assert info['author'] == 'Test Channel'
            assert '720p' in info['quality']
            
    def test_invalid_url(self, extractor):
        """测试无效URL。"""
        url = "invalid_url"
        
        with patch('yt_dlp.YoutubeDL') as mock_ydl:
            # 模拟yt-dlp抛出错误
            mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = \
                Exception("Invalid URL")
                
            # 验证是否抛出预期的异常
            with pytest.raises(ValueError):
                extractor.extract_info(url) 