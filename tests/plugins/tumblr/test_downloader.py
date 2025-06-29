"""tumblr 下载器测试模块。"""

import unittest
from unittest.mock import Mock, patch
from pathlib import Path

import requests

from src.plugins.tumblr.downloader import TumblrDownloader
from src.core.exceptions import DownloadError, NetworkError, AuthError

class TestTumblrDownloader(unittest.TestCase):
    """tumblr 下载器测试类。"""
    
    def setUp(self):
        """测试准备。"""
        self.config = Mock()
        self.config.save_dir = Path("./downloads")
        self.config.proxy = None
        self.config.timeout = 30
        self.config.max_retries = 3
        self.config.cookie_manager = None
        self.config.tumblr_api_key = "test_api_key"
        
        self.downloader = TumblrDownloader(self.config)
        
    def test_validate_url(self):
        """测试URL验证。"""
        # 有效URL
        valid_urls = [
            "https://test.tumblr.com/post/12345",
            "http://blog.tumblr.com/post/67890",
            "https://example.tumblr.com/post/11111"
        ]
        for url in valid_urls:
            self.assertTrue(
                self.downloader._validate_url(url),
                f"应该接受有效URL: {url}"
            )
            
        # 无效URL
        invalid_urls = [
            "https://test.tumblr.com/blog",
            "https://test.tumblr.com/tagged/test",
            "https://other-site.com/post/12345",
            "invalid-url"
        ]
        for url in invalid_urls:
            self.assertFalse(
                self.downloader._validate_url(url),
                f"应该拒绝无效URL: {url}"
            )
            
    def test_parse_post_url(self):
        """测试帖子URL解析。"""
        # 测试有效URL
        url = "https://test.tumblr.com/post/12345"
        blog_name, post_id = self.downloader._parse_post_url(url)
        self.assertEqual(blog_name, "test")
        self.assertEqual(post_id, "12345")
        
        # 测试无效URL
        with self.assertRaises(ValueError):
            self.downloader._parse_post_url("invalid-url")
            
    @patch("requests.Session.get")
    def test_extract_post_info(self, mock_get):
        """测试帖子信息提取。"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {
                "posts": [{
                    "type": "video",
                    "video_url": "https://test.com/video.mp4",
                    "thumbnail_url": "https://test.com/thumb.jpg",
                    "summary": "Test Post"
                }]
            }
        }
        mock_get.return_value = mock_response
        
        # 测试提取
        info = self.downloader.extract_post_info(
            "https://test.tumblr.com/post/12345"
        )
        
        # 验证结果
        self.assertEqual(info["type"], "video")
        self.assertEqual(
            info["video_url"],
            "https://test.com/video.mp4"
        )
        
    @patch("requests.Session.get")
    def test_extract_post_info_network_error(self, mock_get):
        """测试网络错误处理。"""
        # 模拟网络错误
        mock_get.side_effect = requests.exceptions.RequestException()
        
        # 验证异常
        with self.assertRaises(NetworkError):
            self.downloader.extract_post_info(
                "https://test.tumblr.com/post/12345"
            )
            
    @patch("requests.Session.get")
    def test_extract_post_info_auth_error(self, mock_get):
        """测试认证错误处理。"""
        # 模拟认证错误
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        
        # 验证异常
        with self.assertRaises(AuthError):
            self.downloader.extract_post_info(
                "https://test.tumblr.com/post/12345"
            )
            
    def test_extract_media_urls(self):
        """测试媒体URL提取。"""
        # 测试数据
        post = {
            "video_url": "https://test.com/video.mp4",
            "photos": [{
                "original_size": {
                    "url": "https://test.com/photo1.jpg"
                }
            }, {
                "original_size": {
                    "url": "https://test.com/photo2.jpg"
                }
            }]
        }
        
        # 测试提取所有媒体
        urls = self.downloader._extract_media_urls(post, "all")
        self.assertEqual(len(urls), 3)
        self.assertIn("https://test.com/video.mp4", urls)
        self.assertIn("https://test.com/photo1.jpg", urls)
        self.assertIn("https://test.com/photo2.jpg", urls)
        
        # 测试仅提取视频
        urls = self.downloader._extract_media_urls(post, "video")
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], "https://test.com/video.mp4")
        
        # 测试仅提取图片
        urls = self.downloader._extract_media_urls(post, "photo")
        self.assertEqual(len(urls), 2)
        self.assertIn("https://test.com/photo1.jpg", urls)
        self.assertIn("https://test.com/photo2.jpg", urls)
        
    @patch("src.plugins.tumblr.downloader.TumblrDownloader.extract_post_info")
    @patch("src.core.downloader.BaseDownloader.download")
    def test_download(self, mock_base_download, mock_extract_info):
        """测试下载。"""
        # 模拟帖子信息
        mock_extract_info.return_value = {
            "video_url": "https://test.com/video.mp4",
            "photos": [{
                "original_size": {
                    "url": "https://test.com/photo.jpg"
                }
            }],
            "summary": "Test Post"
        }
        
        # 模拟下载成功
        mock_base_download.return_value = True
        
        # 测试下载
        result = self.downloader.download(
            "https://test.tumblr.com/post/12345"
        )
        
        # 验证结果
        self.assertTrue(result)
        self.assertEqual(mock_base_download.call_count, 2)
        
    @patch("src.plugins.tumblr.downloader.TumblrDownloader.extract_post_info")
    def test_download_no_media(self, mock_extract_info):
        """测试无媒体文件处理。"""
        # 模拟无媒体文件的帖子
        mock_extract_info.return_value = {
            "summary": "Test Post"
        }
        
        # 验证异常
        with self.assertRaises(DownloadError):
            self.downloader.download(
                "https://test.tumblr.com/post/12345"
            )
            
if __name__ == "__main__":
    unittest.main() 