"""xvideos 下载器测试模块。"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from src.plugins.xvideos.downloader import XvideosDownloader
from src.core.exceptions import DownloadError, NetworkError, AuthError

class TestXvideosDownloader(unittest.TestCase):
    """xvideos 下载器测试类。"""
    
    def setUp(self):
        """测试准备。"""
        self.config = Mock()
        self.config.save_dir = Path("./downloads")
        self.config.proxy = None
        self.config.timeout = 30
        self.config.max_retries = 3
        self.config.cookie_manager = None
        
        self.downloader = XvideosDownloader(self.config)
        
    def test_validate_url(self):
        """测试URL验证。"""
        # 有效URL
        valid_urls = [
            "https://www.xvideos.com/video12345",
            "http://xvideos.com/video67890",
            "https://xvideos.com/video11111"
        ]
        for url in valid_urls:
            self.assertTrue(
                self.downloader._validate_url(url),
                f"应该接受有效URL: {url}"
            )
            
        # 无效URL
        invalid_urls = [
            "https://www.xvideos.com/profile/123",
            "https://www.xvideos.com/tags/abc",
            "https://www.other-site.com/video12345",
            "invalid-url"
        ]
        for url in invalid_urls:
            self.assertFalse(
                self.downloader._validate_url(url),
                f"应该拒绝无效URL: {url}"
            )
            
    @patch("requests.Session.get")
    def test_extract_video_info(self, mock_get):
        """测试视频信息提取。"""
        # 模拟响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <script>
                html5player.setVideoTitle('Test Video');
                html5player.setVideoUrlHigh('https://test.com/video.mp4');
                html5player.setThumbUrl('https://test.com/thumb.jpg');
            </script>
            <span class="upload-date">2024-01-01</span>
            <a class="tag">tag1</a>
            <a class="tag">tag2</a>
            <span class="name">uploader</span>
        </html>
        """
        mock_get.return_value = mock_response
        
        # 测试提取
        info = self.downloader.extract_video_info(
            "https://www.xvideos.com/video12345"
        )
        
        # 验证结果
        self.assertEqual(info["title"], "Test Video")
        self.assertEqual(
            info["url"],
            "https://test.com/video.mp4"
        )
        self.assertEqual(
            info["thumbnail"],
            "https://test.com/thumb.jpg"
        )
        
    @patch("requests.Session.get")
    def test_extract_video_info_network_error(self, mock_get):
        """测试网络错误处理。"""
        # 模拟网络错误
        mock_get.side_effect = requests.exceptions.RequestException()
        
        # 验证异常
        with self.assertRaises(NetworkError):
            self.downloader.extract_video_info(
                "https://www.xvideos.com/video12345"
            )
            
    @patch("requests.Session.get")
    def test_extract_video_info_auth_error(self, mock_get):
        """测试认证错误处理。"""
        # 模拟认证错误
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        
        # 验证异常
        with self.assertRaises(AuthError):
            self.downloader.extract_video_info(
                "https://www.xvideos.com/video12345"
            )
            
    @patch("src.plugins.xvideos.downloader.XvideosDownloader.extract_video_info")
    @patch("src.core.downloader.BaseDownloader.download")
    def test_download(self, mock_base_download, mock_extract_info):
        """测试视频下载。"""
        # 模拟视频信息
        mock_extract_info.return_value = {
            "title": "Test Video",
            "url": "https://test.com/video.mp4"
        }
        
        # 模拟下载成功
        mock_base_download.return_value = True
        
        # 测试下载
        result = self.downloader.download(
            "https://www.xvideos.com/video12345"
        )
        
        # 验证结果
        self.assertTrue(result)
        mock_base_download.assert_called_once()
        
    @patch("src.plugins.xvideos.downloader.XvideosDownloader.extract_video_info")
    def test_download_extract_error(self, mock_extract_info):
        """测试提取错误处理。"""
        # 模拟提取错误
        mock_extract_info.side_effect = DownloadError("提取失败")
        
        # 验证异常
        with self.assertRaises(DownloadError):
            self.downloader.download(
                "https://www.xvideos.com/video12345"
            )
            
if __name__ == "__main__":
    unittest.main() 