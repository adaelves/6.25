"""Twitter网络错误测试模块。

测试各种网络错误场景的处理。
"""

import pytest
import requests
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.plugins.twitter.anti_crawl import CloudflareBypass, DownloadError
from src.plugins.twitter.extractor import TwitterExtractor

@pytest.fixture
def temp_file(tmp_path):
    """创建临时文件。"""
    return tmp_path / "test_cookies"

def test_cloudflare_bypass_timeout(temp_file):
    """测试Cloudflare绕过超时。"""
    with patch("undetected_playwright.chromium.launch") as mock_launch:
        mock_browser = MagicMock()
        mock_browser.new_context.side_effect = TimeoutError("连接超时")
        mock_launch.return_value = mock_browser
        
        bypass = CloudflareBypass(cookies_file=temp_file)
        with pytest.raises(DownloadError, match="绕过 Cloudflare 5 秒盾失败: 连接超时"):
            bypass.bypass_5s_challenge("https://twitter.com")

def test_cloudflare_bypass_network_error(temp_file):
    """测试Cloudflare绕过网络错误。"""
    with patch("undetected_playwright.chromium.launch") as mock_launch:
        mock_browser = MagicMock()
        mock_browser.new_context.side_effect = ConnectionError("连接失败")
        mock_launch.return_value = mock_browser
        
        bypass = CloudflareBypass(cookies_file=temp_file)
        with pytest.raises(DownloadError, match="绕过 Cloudflare 5 秒盾失败: 连接失败"):
            bypass.bypass_5s_challenge("https://twitter.com")

def test_cloudflare_bypass_verify_cookies_timeout(temp_file):
    """测试验证cookies超时。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.Timeout("连接超时")
        
        bypass = CloudflareBypass(cookies_file=temp_file)
        assert not bypass._verify_cookies({"cf_clearance": "test"})

def test_cloudflare_bypass_verify_cookies_network_error(temp_file):
    """测试验证cookies网络错误。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.ConnectionError("连接失败")
        
        bypass = CloudflareBypass(cookies_file=temp_file)
        assert not bypass._verify_cookies({"cf_clearance": "test"})

def test_cloudflare_bypass_verify_cookies_http_error(temp_file):
    """测试验证cookies HTTP错误。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.HTTPError("403 Forbidden")
        
        bypass = CloudflareBypass(cookies_file=temp_file)
        assert not bypass._verify_cookies({"cf_clearance": "test"})

def test_twitter_extractor_timeout():
    """测试Twitter视频提取超时。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.Timeout("连接超时")
        
        extractor = TwitterExtractor()
        with pytest.raises(DownloadError, match="获取视频信息失败: 连接超时"):
            extractor.extract_video("https://twitter.com/user/status/123456")

def test_twitter_extractor_network_error():
    """测试Twitter视频提取网络错误。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.ConnectionError("连接失败")
        
        extractor = TwitterExtractor()
        with pytest.raises(DownloadError, match="获取视频信息失败: 连接失败"):
            extractor.extract_video("https://twitter.com/user/status/123456")

def test_twitter_extractor_http_error():
    """测试Twitter视频提取HTTP错误。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.HTTPError("404 Not Found")
        
        extractor = TwitterExtractor()
        with pytest.raises(DownloadError, match="获取视频信息失败: 404 Not Found"):
            extractor.extract_video("https://twitter.com/user/status/123456")

def test_twitter_extractor_cloudflare_error():
    """测试遇到Cloudflare检测。"""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = "challenge-platform"
        mock_get.return_value = mock_response
        
        extractor = TwitterExtractor()
        with pytest.raises(DownloadError, match="需要绕过 Cloudflare 检测"):
            extractor.extract_video("https://twitter.com/user/status/123456")

def test_twitter_extractor_invalid_response():
    """测试无效的API响应。"""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("无效的JSON")
        mock_get.return_value = mock_response
        
        extractor = TwitterExtractor()
        with pytest.raises(DownloadError, match="解析视频信息失败: 无效的JSON"):
            extractor.extract_video("https://twitter.com/user/status/123456") 