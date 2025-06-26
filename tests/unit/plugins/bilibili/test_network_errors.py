"""B站网络错误测试模块。

测试各种网络错误场景的处理。
"""

import pytest
import requests
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.plugins.bilibili.danmaku import download_danmaku, DanmakuError
from src.plugins.bilibili.sign import WBIKeyManager
from src.plugins.bilibili.extractor import BilibiliExtractor

@pytest.fixture
def temp_file(tmp_path):
    """创建临时文件。"""
    return tmp_path / "test.xml"

def test_danmaku_download_timeout(temp_file):
    """测试弹幕下载超时。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.Timeout("连接超时")
        
        with pytest.raises(DanmakuError, match="弹幕下载失败: 连接超时"):
            download_danmaku("12345", temp_file)

def test_danmaku_download_connection_error(temp_file):
    """测试弹幕下载连接错误。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.ConnectionError("连接失败")
        
        with pytest.raises(DanmakuError, match="弹幕下载失败: 连接失败"):
            download_danmaku("12345", temp_file)

def test_danmaku_download_http_error(temp_file):
    """测试弹幕下载HTTP错误。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.HTTPError("404 Not Found")
        
        with pytest.raises(DanmakuError, match="弹幕下载失败: 404 Not Found"):
            download_danmaku("12345", temp_file)

def test_danmaku_download_invalid_xml(temp_file):
    """测试无效的XML响应。"""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = "不是XML格式的数据"
        mock_get.return_value = mock_response
        
        with pytest.raises(DanmakuError, match="返回数据不是有效的XML格式"):
            download_danmaku("12345", temp_file)

def test_wbi_key_network_error():
    """测试WBI密钥获取网络错误。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.ConnectionError("连接失败")
        
        manager = WBIKeyManager()
        keys = manager.get_keys()
        
        # 应该返回备用密钥
        assert keys["img_key"] == WBIKeyManager._FALLBACK_IMG_KEY
        assert keys["sub_key"] == WBIKeyManager._FALLBACK_SUB_KEY

def test_wbi_key_timeout():
    """测试WBI密钥获取超时。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.Timeout("连接超时")
        
        manager = WBIKeyManager()
        keys = manager.get_keys()
        
        # 应该返回备用密钥
        assert keys["img_key"] == WBIKeyManager._FALLBACK_IMG_KEY
        assert keys["sub_key"] == WBIKeyManager._FALLBACK_SUB_KEY

def test_wbi_key_http_error():
    """测试WBI密钥获取HTTP错误。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.HTTPError("403 Forbidden")
        
        manager = WBIKeyManager()
        keys = manager.get_keys()
        
        # 应该返回备用密钥
        assert keys["img_key"] == WBIKeyManager._FALLBACK_IMG_KEY
        assert keys["sub_key"] == WBIKeyManager._FALLBACK_SUB_KEY

def test_video_info_network_error():
    """测试视频信息获取网络错误。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.ConnectionError("连接失败")
        
        extractor = BilibiliExtractor()
        with pytest.raises(RuntimeError, match="获取视频信息失败: 连接失败"):
            extractor.get_video_info("BV1xx411c7mD")

def test_video_info_timeout():
    """测试视频信息获取超时。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.Timeout("连接超时")
        
        extractor = BilibiliExtractor()
        with pytest.raises(RuntimeError, match="获取视频信息失败: 连接超时"):
            extractor.get_video_info("BV1xx411c7mD")

def test_video_info_http_error():
    """测试视频信息获取HTTP错误。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.HTTPError("403 Forbidden")
        
        extractor = BilibiliExtractor()
        with pytest.raises(RuntimeError, match="获取视频信息失败: 403 Forbidden"):
            extractor.get_video_info("BV1xx411c7mD") 