"""B站签名测试模块。

测试签名生成和验证功能。
"""

import time
import pytest
import os
import json
import responses
from pathlib import Path
from unittest.mock import patch, MagicMock
import asyncio
import requests

from src.plugins.bilibili.sign import BiliWbiSign

@pytest.fixture
def signer():
    """创建签名器实例。"""
    return BiliWbiSign()

@patch('time.time')
def test_sign_expiry(mock_time, signer):
    """测试签名时效性。"""
    # 设置初始时间
    mock_time.return_value = 1000000000
    
    # 准备测试参数
    params = {
        "aid": "114514",
        "bvid": "BV1xx411c7mD",
        "cid": "12345678"
    }
    
    # 生成第一个签名
    old_sign = signer.sign(params)
    
    # 模拟时间流逝（61秒后）
    mock_time.return_value = 1000000061
    
    # 生成新签名
    new_sign = signer.sign(params)
    
    # 验证签名不同
    assert old_sign != new_sign, "超过有效期后签名应该不同"
    
@pytest.mark.parametrize("params", [
    {"aid": "114514"},
    {"bvid": "BV1xx411c7mD"},
    {"aid": "114514", "bvid": "BV1xx411c7mD"},
    {"aid": "114514", "bvid": "BV1xx411c7mD", "cid": "12345678"}
])
def test_sign_consistency(signer, params):
    """测试相同参数的签名一致性。"""
    # 连续生成两个签名(间隔很短)
    sign1 = signer.sign(params)
    sign2 = signer.sign(params)
    
    # 验证签名相同
    assert sign1 == sign2, "短时间内相同参数应生成相同签名"
    
def test_sign_parameter_order(signer):
    """测试参数顺序对签名的影响。"""
    params1 = {
        "aid": "114514",
        "bvid": "BV1xx411c7mD",
        "cid": "12345678"
    }
    
    params2 = {
        "bvid": "BV1xx411c7mD",
        "cid": "12345678",
        "aid": "114514"
    }
    
    sign1 = signer.sign(params1)
    sign2 = signer.sign(params2)
    
    assert sign1 == sign2, "参数顺序不同应生成相同签名"
    
def test_sign_empty_params(signer):
    """测试空参数签名。"""
    sign = signer.sign({})
    assert sign, "空参数也应该生成有效签名"
    
@pytest.mark.parametrize("invalid_params", [
    None,
    "invalid",
    123,
    ["aid", "bvid"],
    {"aid": None},
    {"aid": b"114514"}
])
def test_sign_invalid_params(signer, invalid_params):
    """测试无效参数签名。"""
    with pytest.raises(ValueError):
        signer.sign(invalid_params)
        
@patch('time.time')
def test_sign_timestamp(mock_time, signer):
    """测试签名中的时间戳。"""
    # 设置固定时间
    test_time = 1000000000
    mock_time.return_value = test_time
    
    params = {"aid": "114514"}
    signed_params = signer.sign(params)
    
    # 验证时间戳
    assert signed_params['wts'] == str(test_time), \
        "签名中的时间戳应该与当前时间一致"

@pytest.fixture
def mock_nav_response():
    """模拟导航API响应。"""
    return {
        "code": 0,
        "message": "0",
        "ttl": 1,
        "data": {
            "wbi_img": {
                "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
                "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"
            }
        }
    }

@pytest.fixture
def mock_nav_error_response():
    """模拟导航API错误响应。"""
    return {
        "code": -401,
        "message": "未登录",
        "ttl": 1
    }

@pytest.fixture
def temp_cache_file(tmp_path):
    """创建临时缓存文件。"""
    cache_file = tmp_path / "test_wbi_keys"
    return cache_file

def test_verify_keys():
    """测试密钥验证功能。"""
    # 测试有效密钥
    assert BiliWbiSign._verify_keys(
        "7cd084941338484aae1ad9425b84077c",
        "4932caff0ff746eab6f01bf08b70ac45"
    )
    
    # 测试无效密钥（长度错误）
    assert not BiliWbiSign._verify_keys("invalid", "keys")
    assert not BiliWbiSign._verify_keys("", "")
    
    # 测试无效密钥（非16进制字符）
    assert not BiliWbiSign._verify_keys(
        "7cd084941338484aae1ad9425b84077g",  # g不是16进制字符
        "4932caff0ff746eab6f01bf08b70ac45"
    )
    
@responses.activate
def test_fetch_new_keys(mock_nav_response):
    """测试获取新密钥。"""
    # 模拟API响应
    responses.add(
        responses.GET,
        "https://api.bilibili.com/x/web-interface/nav",
        json=mock_nav_response,
        status=200
    )
    
    signer = BiliWbiSign()
    img_key, sub_key = signer.get_keys()
    
    assert img_key == "7cd084941338484aae1ad9425b84077c"
    assert sub_key == "4932caff0ff746eab6f01bf08b70ac45"
    
@responses.activate
def test_fallback_to_old_keys(mock_nav_response, mock_nav_error_response):
    """测试失败时使用旧密钥。"""
    # 第一次请求成功
    responses.add(
        responses.GET,
        "https://api.bilibili.com/x/web-interface/nav",
        json=mock_nav_response,
        status=200
    )
    
    # 第二次请求失败
    responses.add(
        responses.GET,
        "https://api.bilibili.com/x/web-interface/nav",
        json=mock_nav_error_response,
        status=401
    )
    
    signer = BiliWbiSign()
    
    # 第一次获取密钥
    img_key1, sub_key1 = signer.get_keys()
    
    # 修改更新时间以触发刷新
    BiliWbiSign._last_update = 0
    
    # 第二次获取密钥（应该使用旧密钥）
    img_key2, sub_key2 = signer.get_keys()
    
    assert img_key1 == img_key2
    assert sub_key1 == sub_key2
    
@responses.activate
def test_fallback_to_hardcoded_keys(mock_nav_error_response):
    """测试使用硬编码的备用密钥。"""
    # 模拟API始终失败
    responses.add(
        responses.GET,
        "https://api.bilibili.com/x/web-interface/nav",
        json=mock_nav_error_response,
        status=401
    )
    
    signer = BiliWbiSign()
    img_key, sub_key = signer.get_keys()
    
    assert img_key == BiliWbiSign._FALLBACK_IMG_KEY
    assert sub_key == BiliWbiSign._FALLBACK_SUB_KEY
    
def test_key_cache(temp_cache_file):
    """测试密钥缓存功能。"""
    # 创建测试缓存
    test_data = {
        "img_key": "7cd084941338484aae1ad9425b84077c",
        "sub_key": "4932caff0ff746eab6f01bf08b70ac45",
        "timestamp": time.time()
    }
    
    with open(temp_cache_file, "w") as f:
        json.dump(test_data, f)
        
    # 使用测试缓存文件创建签名器
    signer = BiliWbiSign(cache_file=temp_cache_file)
    
    # 验证加载的密钥
    assert signer._img_key == test_data["img_key"]
    assert signer._sub_key == test_data["sub_key"]
    
def test_key_cache_expiry(temp_cache_file):
    """测试密钥缓存过期。"""
    # 创建过期的测试缓存
    test_data = {
        "img_key": "7cd084941338484aae1ad9425b84077c",
        "sub_key": "4932caff0ff746eab6f01bf08b70ac45",
        "timestamp": time.time() - 7200  # 2小时前
    }
    
    with open(temp_cache_file, "w") as f:
        json.dump(test_data, f)
        
    # 使用测试缓存文件创建签名器
    signer = BiliWbiSign(cache_file=temp_cache_file)
    
    # 验证密钥未被加载（因为已过期）
    assert not signer._img_key
    assert not signer._sub_key
    
@responses.activate
def test_concurrent_key_updates(mock_nav_response):
    """测试并发密钥更新。"""
    # 模拟API响应
    responses.add(
        responses.GET,
        "https://api.bilibili.com/x/web-interface/nav",
        json=mock_nav_response,
        status=200
    )
    
    # 创建多个签名器实例
    signers = [BiliWbiSign() for _ in range(5)]
    
    # 同时获取密钥
    keys = [signer.get_keys() for signer in signers]
    
    # 验证所有实例获取到相同的密钥
    assert all(k == keys[0] for k in keys)
    
def test_sign_with_fallback():
    """测试使用备用密钥签名。"""
    signer = BiliWbiSign()
    signer._use_fallback = True
    signer._img_key = BiliWbiSign._FALLBACK_IMG_KEY
    signer._sub_key = BiliWbiSign._FALLBACK_SUB_KEY
    
    params = {"foo": "bar"}
    signed_params = signer.sign(params)
    
    assert "w_rid" in signed_params
    assert "wts" in signed_params
    
@patch('time.time')
def test_key_refresh_interval(mock_time):
    """测试密钥刷新间隔。"""
    # 设置初始时间
    mock_time.return_value = 1000000000
    
    signer = BiliWbiSign(key_ttl=1)  # 1秒后过期
    
    # 第一次获取密钥
    signer._update_keys_if_needed()
    keys1 = (signer._img_key, signer._sub_key)
    
    # 模拟时间流逝（1.1秒后）
    mock_time.return_value = 1000000001.1
    
    # 第二次获取密钥
    signer._update_keys_if_needed()
    keys2 = (signer._img_key, signer._sub_key)
    
    # 验证密钥已更新
    assert keys1 != keys2, "密钥应该已更新" 

@patch('time.time')
@patch('requests.get')
def test_class_get_keys(mock_get, mock_time):
    """测试类方法 get_keys() 的行为。"""
    # 重置类级别的缓存
    BiliWbiSign._wbi_keys = None
    BiliWbiSign._last_update = 0
    
    # 设置初始时间
    mock_time.return_value = 1000000000
    
    # 模拟成功的API响应
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "data": {
            "wbi_img": {
                "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
                "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"
            }
        }
    }
    mock_get.return_value = mock_response
    
    # 第一次获取密钥
    keys1 = BiliWbiSign.get_keys()
    assert len(keys1) == 2, "应该返回两个密钥"
    assert all(len(key) == 32 for key in keys1), "密钥长度应该是32位"
    assert all(all(c in "0123456789abcdef" for c in key) for key in keys1), "密钥应该是16进制字符串"
    
    # 验证API只被调用一次
    mock_get.assert_called_once()
    
    # 未到1小时，再次获取密钥
    mock_time.return_value = 1000003599  # 3599秒后（1小时内）
    keys2 = BiliWbiSign.get_keys()
    assert keys1 == keys2, "1小时内应该返回缓存的密钥"
    assert mock_get.call_count == 1, "1小时内不应该重新请求API"
    
    # 超过1小时，再次获取密钥
    mock_time.return_value = 1000003601  # 3601秒后（超过1小时）
    keys3 = BiliWbiSign.get_keys()
    assert keys3 != keys1, "超过1小时后应该获取新密钥"
    assert mock_get.call_count == 2, "应该重新请求API"
    
    # 测试API失败时的备用密钥机制
    mock_get.side_effect = requests.RequestException("API请求失败")
    keys4 = BiliWbiSign.get_keys()
    assert keys4 == (BiliWbiSign._FALLBACK_IMG_KEY, BiliWbiSign._FALLBACK_SUB_KEY), "API失败时应该使用备用密钥"
    
    # 如果有缓存的密钥，API失败时应该继续使用缓存的密钥
    mock_time.return_value = 1000007200  # 再过1小时
    BiliWbiSign._wbi_keys = keys3  # 手动设置缓存的密钥
    keys5 = BiliWbiSign.get_keys()
    assert keys5 == keys3, "有缓存密钥时，API失败应该继续使用缓存的密钥" 