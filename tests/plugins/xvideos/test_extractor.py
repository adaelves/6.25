"""xvideos 提取器测试模块。"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from src.plugins.xvideos.extractor import XvideosExtractor
from src.core.exceptions import ExtractError

class TestXvideosExtractor(unittest.TestCase):
    """xvideos 提取器测试类。"""
    
    def setUp(self):
        """测试准备。"""
        self.extractor = XvideosExtractor()
        
    def test_validate_url(self):
        """测试URL验证。"""
        # 有效URL
        valid_urls = [
            "https://www.xvideos.com/video12345",
            "http://xvideos.com/video67890",
            "https://xvideos.com/channels/test",
            "https://www.xvideos.com/pornstars/test"
        ]
        for url in valid_urls:
            self.assertTrue(
                self.extractor.validate_url(url),
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
                self.extractor.validate_url(url),
                f"应该拒绝无效URL: {url}"
            )
            
    def test_extract_video_id(self):
        """测试视频ID提取。"""
        # 测试视频URL
        url = "https://www.xvideos.com/video12345"
        video_id = self.extractor._extract_video_id(url)
        self.assertEqual(video_id, "12345")
        
        # 测试频道URL
        url = "https://www.xvideos.com/channels/test"
        video_id = self.extractor._extract_video_id(url)
        self.assertIsNone(video_id)
        
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
                html5player.setVideoDuration(120);
            </script>
            <span class="upload-date">2024-01-01</span>
            <a class="tag">tag1</a>
            <a class="tag">tag2</a>
            <span class="name">
                <a href="/uploader">uploader</a>
            </span>
        </html>
        """
        mock_get.return_value = mock_response
        
        # 测试提取
        info = self.extractor._extract_video_info(
            mock_response.text,
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
        self.assertEqual(info["duration"], 120)
        self.assertEqual(info["tags"], ["tag1", "tag2"])
        self.assertEqual(info["uploader"], "uploader")
        self.assertEqual(info["uploader_url"], "/uploader")
        
    @patch("requests.Session.get")
    def test_extract_video_info_missing_data(self, mock_get):
        """测试缺失数据处理。"""
        # 模拟响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html></html>"
        mock_get.return_value = mock_response
        
        # 验证异常
        with self.assertRaises(ExtractError):
            self.extractor._extract_video_info(
                mock_response.text,
                "https://www.xvideos.com/video12345"
            )
            
    @patch("requests.Session.get")
    def test_extract(self, mock_get):
        """测试信息提取。"""
        # 模拟响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <script>
                html5player.setVideoTitle('Test Video');
                html5player.setVideoUrlHigh('https://test.com/video.mp4');
                html5player.setThumbUrl('https://test.com/thumb.jpg');
                html5player.setVideoDuration(120);
            </script>
            <span class="upload-date">2024-01-01</span>
            <a class="tag">tag1</a>
            <a class="tag">tag2</a>
            <span class="name">uploader</span>
        </html>
        """
        mock_get.return_value = mock_response
        
        # 测试提取
        info = self.extractor.extract(
            "https://www.xvideos.com/video12345"
        )
        
        # 验证结果
        self.assertEqual(info["title"], "Test Video")
        self.assertEqual(info["extractor"], "xvideos")
        self.assertEqual(info["extractor_key"], "Xvideos")
        
    @patch("requests.Session.get")
    def test_extract_network_error(self, mock_get):
        """测试网络错误处理。"""
        # 模拟网络错误
        mock_get.side_effect = requests.exceptions.RequestException()
        
        # 验证异常
        with self.assertRaises(ExtractError):
            self.extractor.extract(
                "https://www.xvideos.com/video12345"
            )
            
if __name__ == "__main__":
    unittest.main() 