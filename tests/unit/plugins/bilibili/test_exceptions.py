"""B站异常处理测试模块。

该模块包含对B站相关异常的单元测试。
"""

import pytest
from core.exceptions import (
    BiliBiliError,
    VIPContentError,
    RegionLockError,
    NetworkError,
    ParsingError,
    RateLimitError
)

def test_bilibili_error_base():
    """测试基础异常类。"""
    error = BiliBiliError("测试错误", 1001)
    assert str(error) == "测试错误"
    assert error.code == 1001
    
    # 测试默认消息
    error = BiliBiliError()
    assert str(error) == "B站API调用出错"
    
def test_vip_content_error():
    """测试大会员专享内容错误。"""
    error = VIPContentError()
    assert "大会员权限" in str(error)
    assert "登录" in str(error)
    
    # 测试自定义消息
    custom_msg = "此视频需要大会员观看"
    error = VIPContentError(custom_msg)
    assert str(error) == custom_msg
    
def test_region_lock_error():
    """测试地区限制错误。"""
    error = RegionLockError()
    assert "地区不可用" in str(error)
    assert "代理服务器" in str(error)
    assert "香港" in str(error) or "台湾" in str(error)
    
def test_network_error():
    """测试网络错误。"""
    error = NetworkError()
    assert "网络" in str(error)
    assert "代理服务器" in str(error)
    
    # 测试超时错误
    error = NetworkError("请求超时")
    assert "超时" in str(error)
    
def test_parsing_error():
    """测试解析错误。"""
    error = ParsingError()
    assert "解析失败" in str(error)
    
    # 测试JSON解析错误
    error = ParsingError("JSON格式错误")
    assert "JSON" in str(error)
    
def test_rate_limit_error():
    """测试请求频率限制错误。"""
    error = RateLimitError()
    assert "频繁" in str(error)
    assert "IP" in str(error)
    
def test_error_inheritance():
    """测试异常继承关系。"""
    # 所有异常都应该继承自BiliBiliError
    assert issubclass(VIPContentError, BiliBiliError)
    assert issubclass(RegionLockError, BiliBiliError)
    assert issubclass(NetworkError, BiliBiliError)
    assert issubclass(ParsingError, BiliBiliError)
    assert issubclass(RateLimitError, BiliBiliError)
    
def test_error_code_handling():
    """测试错误代码处理。"""
    # 测试不同的错误代码
    error = BiliBiliError("测试错误", -404)
    assert error.code == -404
    
    error = BiliBiliError("测试错误", 62002)
    assert error.code == 62002
    
def test_error_messages():
    """测试错误消息格式。"""
    # 测试所有错误类的消息都包含解决方案
    errors = [
        VIPContentError(),
        RegionLockError(),
        NetworkError(),
        ParsingError(),
        RateLimitError()
    ]
    
    for error in errors:
        message = str(error)
        # 检查消息是否包含解决方案提示
        assert any(
            hint in message.lower()
            for hint in ["请", "可以", "建议", "尝试", "检查"]
        ), f"{error.__class__.__name__} 的错误消息应该包含解决方案提示" 