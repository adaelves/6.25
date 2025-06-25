#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""YouTube下载器单元测试。"""

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from plugins.youtube import YouTubeDownloader
from plugins.youtube.extractor import YouTubeExtractor

class TestYouTubeExtractor(unittest.TestCase):
    """YouTube信息提取器测试类。"""
    
    def setUp(self) -> None:
        """测试前置设置。"""
        self.extractor = YouTubeExtractor()
        self.test_url = "https://www.youtube.com/watch?v=test_id"
        
    @patch('yt_dlp.YoutubeDL')
    def test_extract_info_success(self, mock_ydl) -> None:
        """测试成功提取视频信息。"""
        # 模拟返回数据
        mock_info = {
            'title': '测试视频',
            'uploader': '测试作者',
            'formats': [
                {'height': 1080},
                {'height': 720}
            ],
            'view_count': 1000,
            'like_count': 100,
            'duration': 300
        }
        
        # 设置mock
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl.return_value.__enter__.return_value = mock_ydl_instance
        
        # 执行测试
        info = self.extractor.extract_info(self.test_url)
        
        # 验证结果
        self.assertEqual(info['title'], '测试视频')
        self.assertEqual(info['author'], '测试作者')
        self.assertEqual(set(info['quality']), {'1080p', '720p'})
        self.assertEqual(info['view_count'], 1000)
        self.assertEqual(info['like_count'], 100)
        self.assertEqual(info['duration'], 300)
        
    @patch('yt_dlp.YoutubeDL')
    def test_extract_info_with_age_limit(self, mock_ydl) -> None:
        """测试提取年龄限制视频信息。"""
        # 模拟返回数据
        mock_info_with_age = {'age_limit': 18}
        mock_info = {
            'title': '限制级视频',
            'uploader': '测试作者',
            'formats': [{'height': 1080}],
            'age_limit': 18
        }
        
        # 设置mock
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.side_effect = [mock_info_with_age, mock_info]
        mock_ydl.return_value.__enter__.return_value = mock_ydl_instance
        
        # 执行测试
        info = self.extractor.extract_info(self.test_url)
        
        # 验证结果
        self.assertEqual(info['title'], '限制级视频')
        self.assertTrue('1080p' in info['quality'])

class TestYouTubeDownloader(unittest.TestCase):
    """YouTube下载器测试类。"""
    
    def setUp(self) -> None:
        """测试前置设置。"""
        self.downloader = YouTubeDownloader()
        self.test_url = "https://www.youtube.com/watch?v=test_id"
        self.test_path = Path("test_video.mp4")
        
    @patch('plugins.youtube.extractor.YouTubeExtractor')
    def test_get_video_info(self, mock_extractor_class) -> None:
        """测试获取视频信息。"""
        # 模拟返回数据
        mock_info = {
            'title': '测试视频',
            'author': '测试作者',
            'quality': ['1080p', '720p']
        }
        
        # 设置mock
        mock_extractor = MagicMock()
        mock_extractor.extract_info.return_value = mock_info
        mock_extractor_class.return_value = mock_extractor
        
        # 执行测试
        info = self.downloader.get_video_info(self.test_url)
        
        # 验证结果
        self.assertEqual(info, mock_info)
        mock_extractor.extract_info.assert_called_once_with(self.test_url)
        
    @patch('yt_dlp.YoutubeDL')
    def test_download_success(self, mock_ydl) -> None:
        """测试成功下载视频。"""
        # 设置mock
        mock_ydl_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_ydl_instance
        
        # 执行测试
        result = self.downloader.download(self.test_url, self.test_path)
        
        # 验证结果
        self.assertTrue(result)
        mock_ydl_instance.download.assert_called_once_with([self.test_url])
        
    @patch('yt_dlp.YoutubeDL')
    def test_download_failure(self, mock_ydl) -> None:
        """测试下载失败的情况。"""
        # 设置mock抛出异常
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.download.side_effect = Exception("下载失败")
        mock_ydl.return_value.__enter__.return_value = mock_ydl_instance
        
        # 执行测试
        result = self.downloader.download(self.test_url, self.test_path)
        
        # 验证结果
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main() 