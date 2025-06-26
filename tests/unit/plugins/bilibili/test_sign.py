"""B站WBI密钥管理器测试模块。"""

import os
import json
import time
import pytest
import requests
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.plugins.bilibili.sign import WBIKeyManager

@pytest.fixture
def temp_cache_dir(tmp_path):
    """创建临时缓存目录。"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return str(cache_dir)

@pytest.fixture
def mock_response():
    """模拟API响应。"""
    return {
        "code": 0,
        "data": {
            "wbi_img": {
                "key": "test_img_key",
                "sub_key": "test_sub_key"
            }
        }
    }

def test_init(temp_cache_dir):
    """测试初始化。"""
    manager = WBIKeyManager(cache_dir=temp_cache_dir)
    assert manager.cache_file.exists()
    assert manager.cache_ttl == 3600

def test_fetch_keys_success(temp_cache_dir, mock_response):
    """测试成功获取密钥。"""
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        manager = WBIKeyManager(cache_dir=temp_cache_dir)
        keys = manager._fetch_wbi_keys()
        
        assert keys["img_key"] == "test_img_key"
        assert keys["sub_key"] == "test_sub_key"
        mock_get.assert_called_once()

def test_fetch_keys_api_error(temp_cache_dir):
    """测试API返回错误。"""
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = {
            "code": -1,
            "message": "API错误"
        }
        manager = WBIKeyManager(cache_dir=temp_cache_dir)
        
        with pytest.raises(ValueError, match="API返回错误"):
            manager._fetch_wbi_keys()

def test_fetch_keys_network_error(temp_cache_dir):
    """测试网络错误。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.RequestException("网络错误")
        manager = WBIKeyManager(cache_dir=temp_cache_dir)
        
        with pytest.raises(requests.RequestException):
            manager._fetch_wbi_keys()

def test_cache_save_and_load(temp_cache_dir, mock_response):
    """测试密钥缓存的保存和加载。"""
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        manager = WBIKeyManager(cache_dir=temp_cache_dir)
        
        # 获取并缓存密钥
        keys = manager.get_keys()
        assert keys["img_key"] == "test_img_key"
        assert keys["sub_key"] == "test_sub_key"
        
        # 验证缓存文件
        assert manager.cache_file.exists()
        with open(manager.cache_file) as f:
            cache_data = json.load(f)
        assert "timestamp" in cache_data
        assert cache_data["keys"] == keys
        
        # 创建新的管理器实例
        new_manager = WBIKeyManager(cache_dir=temp_cache_dir)
        cached_keys = new_manager.get_keys()
        assert cached_keys == keys

def test_expired_cache(temp_cache_dir, mock_response):
    """测试过期缓存处理。"""
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        manager = WBIKeyManager(cache_dir=temp_cache_dir, cache_ttl=1)
        
        # 获取并缓存密钥
        keys = manager.get_keys()
        
        # 等待缓存过期
        time.sleep(2)
        
        # 模拟网络错误
        mock_get.side_effect = requests.RequestException("网络错误")
        
        # 应该返回过期的缓存密钥
        expired_keys = manager.get_keys()
        assert expired_keys == keys

def test_no_cache_network_error(temp_cache_dir):
    """测试无缓存时的网络错误处理。"""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.RequestException("网络错误")
        manager = WBIKeyManager(cache_dir=temp_cache_dir)
        
        # 应该返回备用密钥
        keys = manager.get_keys()
        assert keys["img_key"] == WBIKeyManager._FALLBACK_IMG_KEY
        assert keys["sub_key"] == WBIKeyManager._FALLBACK_SUB_KEY

def test_invalid_cache_format(temp_cache_dir, mock_response):
    """测试无效的缓存格式处理。"""
    manager = WBIKeyManager(cache_dir=temp_cache_dir)
    
    # 写入无效的缓存数据
    with open(manager.cache_file, "w") as f:
        f.write("invalid json")
        
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        keys = manager.get_keys()
        assert keys["img_key"] == "test_img_key"
        assert keys["sub_key"] == "test_sub_key"

@patch('time.time')
def test_sign_params(mock_time, temp_cache_dir, mock_response):
    """测试参数签名。"""
    # 设置固定时间
    test_time = 1000000000
    mock_time.return_value = test_time
    
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        manager = WBIKeyManager(cache_dir=temp_cache_dir)
        
        # 准备测试参数
        params = {
            "aid": "114514",
            "bvid": "BV1xx411c7mD"
        }
        
        # 签名参数
        signed_params = manager.sign(params)
        
        # 验证时间戳
        assert signed_params["wts"] == str(test_time)
        
        # 验证签名存在
        assert "w_rid" in signed_params
        assert len(signed_params["w_rid"]) == 32
        assert all(c in "0123456789abcdef" for c in signed_params["w_rid"])
        
        # 验证原始参数未被修改
        assert "wts" not in params
        assert "w_rid" not in params

@pytest.mark.parametrize("invalid_params", [
    None,
    "invalid",
    123,
    ["aid", "bvid"],
    {"aid": None}
])
def test_sign_invalid_params(temp_cache_dir, invalid_params):
    """测试无效参数签名。"""
    manager = WBIKeyManager(cache_dir=temp_cache_dir)
    with pytest.raises(ValueError, match="参数必须是字典类型"):
        manager.sign(invalid_params)

def test_sign_parameter_order(temp_cache_dir, mock_response):
    """测试参数顺序对签名的影响。"""
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        manager = WBIKeyManager(cache_dir=temp_cache_dir)
        
        params1 = {
            "aid": "114514",
            "bvid": "BV1xx411c7mD"
        }
        
        params2 = {
            "bvid": "BV1xx411c7mD",
            "aid": "114514"
        }
        
        # 在相同时间点签名
        with patch('time.time', return_value=1000000000):
            sign1 = manager.sign(params1)
            sign2 = manager.sign(params2)
        
        # 验证签名相同
        assert sign1["w_rid"] == sign2["w_rid"]

def test_sign_empty_params(temp_cache_dir, mock_response):
    """测试空参数签名。"""
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        manager = WBIKeyManager(cache_dir=temp_cache_dir)
        
        signed_params = manager.sign({})
        assert "wts" in signed_params
        assert "w_rid" in signed_params 