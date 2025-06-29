"""tumblr 提取器测试模块。"""

import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any

import requests

from src.plugins.tumblr.extractor import TumblrExtractor
from src.core.exceptions import ExtractError

class TestTumblrExtractor(unittest.TestCase):
    """tumblr 提取器测试类。"""
    
    def setUp(self):
        """测试准备。"""
        self.api_key = "test_api_key"
        self.extractor = TumblrExtractor(api_key=self.api_key)
        
    def test_validate_url(self):
        """测试URL验证。"""
        # 有效URL
        valid_urls = [
            "https://test.tumblr.com/post/12345",
            "http://blog.tumblr.com/post/67890",
            "https://test.tumblr.com/tagged/test"
        ]
        for url in valid_urls:
            self.assertTrue(
                self.extractor.validate_url(url),
                f"应该接受有效URL: {url}"
            )
            
        # 无效URL
        invalid_urls = [
            "https://test.tumblr.com/blog",
            "https://other-site.com/post/12345",
            "invalid-url"
        ]
        for url in invalid_urls:
            self.assertFalse(
                self.extractor.validate_url(url),
                f"应该拒绝无效URL: {url}"
            )
            
    def test_parse_url(self):
        """测试URL解析。"""
        # 测试帖子URL
        url = "https://test.tumblr.com/post/12345"
        blog_name, post_id, tag = self.extractor._parse_url(url)
        self.assertEqual(blog_name, "test")
        self.assertEqual(post_id, "12345")
        self.assertIsNone(tag)
        
        # 测试标签URL
        url = "https://test.tumblr.com/tagged/test-tag"
        blog_name, post_id, tag = self.extractor._parse_url(url)
        self.assertEqual(blog_name, "test")
        self.assertIsNone(post_id)
        self.assertEqual(tag, "test-tag")
        
        # 测试无效URL
        with self.assertRaises(ValueError):
            self.extractor._parse_url("invalid-url")
            
    @patch("requests.Session.get")
    def test_extract_post(self, mock_get):
        """测试帖子提取。"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {
                "posts": [{
                    "type": "photo",
                    "id": "12345",
                    "blog_name": "test",
                    "title": "Test Post",
                    "summary": "Test Summary",
                    "body": "Test Body",
                    "tags": ["tag1", "tag2"],
                    "date": "2024-01-01",
                    "timestamp": 1704067200,
                    "note_count": 100,
                    "post_url": "https://test.tumblr.com/post/12345",
                    "photos": [{
                        "original_size": {
                            "url": "https://test.com/photo.jpg",
                            "width": 1000,
                            "height": 800
                        }
                    }]
                }]
            }
        }
        mock_get.return_value = mock_response
        
        # 测试提取
        info = self.extractor._extract_post("test", "12345")
        
        # 验证结果
        self.assertEqual(info["id"], "12345")
        self.assertEqual(info["blog_name"], "test")
        self.assertEqual(info["type"], "photo")
        self.assertEqual(info["title"], "Test Post")
        self.assertEqual(info["tags"], ["tag1", "tag2"])
        self.assertEqual(len(info["media"]), 1)
        self.assertEqual(
            info["media"][0]["url"],
            "https://test.com/photo.jpg"
        )
        
    @patch("requests.Session.get")
    def test_extract_post_not_found(self, mock_get):
        """测试帖子不存在处理。"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {
                "posts": []
            }
        }
        mock_get.return_value = mock_response
        
        # 验证异常
        with self.assertRaises(ExtractError):
            self.extractor._extract_post("test", "12345")
            
    @patch("requests.Session.get")
    def test_extract_tagged_posts(self, mock_get):
        """测试标签帖子提取。"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {
                "posts": [{
                    "id": "12345",
                    "type": "photo",
                    "title": "Test Post 1",
                    "summary": "Test Summary 1",
                    "tags": ["tag1"],
                    "date": "2024-01-01",
                    "post_url": "https://test.tumblr.com/post/12345",
                    "photos": [{
                        "original_size": {
                            "url": "https://test.com/photo1.jpg"
                        }
                    }]
                }, {
                    "id": "67890",
                    "type": "video",
                    "title": "Test Post 2",
                    "summary": "Test Summary 2",
                    "tags": ["tag2"],
                    "date": "2024-01-02",
                    "post_url": "https://test.tumblr.com/post/67890",
                    "video_url": "https://test.com/video.mp4"
                }]
            }
        }
        mock_get.return_value = mock_response
        
        # 测试提取
        info = self.extractor._extract_tagged_posts(
            "test",
            "test-tag"
        )
        
        # 验证结果
        self.assertEqual(info["blog_name"], "test")
        self.assertEqual(info["tag"], "test-tag")
        self.assertEqual(info["total_posts"], 2)
        self.assertEqual(len(info["posts"]), 2)
        self.assertEqual(info["posts"][0]["id"], "12345")
        self.assertEqual(info["posts"][1]["id"], "67890")
        
    def test_extract_media_info(self):
        """测试媒体信息提取。"""
        # 测试数据
        post: Dict[str, Any] = {
            "video_url": "https://test.com/video.mp4",
            "thumbnail_url": "https://test.com/thumb.jpg",
            "photos": [{
                "original_size": {
                    "url": "https://test.com/photo1.jpg",
                    "width": 1000,
                    "height": 800
                }
            }, {
                "original_size": {
                    "url": "https://test.com/photo2.jpg",
                    "width": 800,
                    "height": 600
                }
            }]
        }
        
        # 测试提取
        media = self.extractor._extract_media_info(post)
        
        # 验证结果
        self.assertEqual(len(media), 3)
        
        # 验证视频信息
        video = media[0]
        self.assertEqual(video["type"], "video")
        self.assertEqual(video["url"], "https://test.com/video.mp4")
        self.assertEqual(
            video["thumbnail"],
            "https://test.com/thumb.jpg"
        )
        
        # 验证图片信息
        photo1 = media[1]
        self.assertEqual(photo1["type"], "photo")
        self.assertEqual(photo1["url"], "https://test.com/photo1.jpg")
        self.assertEqual(photo1["width"], 1000)
        self.assertEqual(photo1["height"], 800)
        
        photo2 = media[2]
        self.assertEqual(photo2["type"], "photo")
        self.assertEqual(photo2["url"], "https://test.com/photo2.jpg")
        self.assertEqual(photo2["width"], 800)
        self.assertEqual(photo2["height"], 600)
        
    @patch("requests.Session.get")
    def test_extract(self, mock_get):
        """测试信息提取。"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {
                "posts": [{
                    "type": "photo",
                    "id": "12345",
                    "title": "Test Post",
                    "photos": [{
                        "original_size": {
                            "url": "https://test.com/photo.jpg"
                        }
                    }]
                }]
            }
        }
        mock_get.return_value = mock_response
        
        # 测试提取帖子
        info = self.extractor.extract(
            "https://test.tumblr.com/post/12345"
        )
        self.assertEqual(info["id"], "12345")
        self.assertEqual(info["extractor"], "tumblr")
        
        # 测试提取标签
        info = self.extractor.extract(
            "https://test.tumblr.com/tagged/test"
        )
        self.assertEqual(info["tag"], "test")
        self.assertEqual(info["extractor"], "tumblr")
        
    @patch("requests.Session.get")
    def test_extract_network_error(self, mock_get):
        """测试网络错误处理。"""
        # 模拟网络错误
        mock_get.side_effect = requests.exceptions.RequestException()
        
        # 验证异常
        with self.assertRaises(ExtractError):
            self.extractor.extract(
                "https://test.tumblr.com/post/12345"
            )
            
if __name__ == "__main__":
    unittest.main() 