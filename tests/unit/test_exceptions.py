"""异常处理模块的单元测试。

测试覆盖:
1. 基础异常类的创建和属性
2. 网络异常的特殊属性
3. 平台特定异常
4. 异常工厂函数
5. 下载相关异常
"""

import pytest
from datetime import datetime
from src.core.exceptions import (
    PlatformError,
    NetworkError,
    RateLimitError,
    AuthError,
    ParseError,
    TwitterError,
    TwitterRateLimitError,
    TwitterAuthError,
    TwitterParseError,
    BiliError,
    BiliRateLimitError,
    BiliKeyExpiredError,
    BiliAuthError,
    BiliParseError,
    DownloadError,
    DownloadCanceled,
    ResourceNotFoundError,
    create_platform_error,
)

class TestPlatformError:
    """测试基础平台异常类。"""
    
    def test_basic_error(self):
        """测试基本异常创建。"""
        error = PlatformError("test", "测试错误")
        assert error.platform == "test"
        assert error.msg == "[test] 测试错误"
        assert error.code is None
        assert error.data == {}
        
    def test_error_with_code(self):
        """测试带错误码的异常。"""
        error = PlatformError("test", "测试错误", code=404)
        assert error.code == 404
        assert "code=404" in str(error)
        
    def test_error_with_data(self):
        """测试带附加数据的异常。"""
        data = {"url": "https://example.com"}
        error = PlatformError("test", "测试错误", data=data)
        assert error.data == data

class TestNetworkError:
    """测试网络异常类。"""
    
    def test_basic_network_error(self):
        """测试基本网络异常。"""
        error = NetworkError("test", "网络错误")
        assert error.retry_after is None
        
    def test_network_error_with_retry(self):
        """测试带重试时间的网络异常。"""
        error = NetworkError("test", "请求限制", retry_after=60.0)
        assert error.retry_after == 60.0
        assert "retry after 60.0s" in str(error)

class TestTwitterExceptions:
    """测试Twitter相关异常。"""
    
    def test_twitter_basic_error(self):
        """测试Twitter基本异常。"""
        error = TwitterError("推文不存在")
        assert error.platform == "twitter"
        assert "推文不存在" in str(error)
        
    def test_twitter_rate_limit(self):
        """测试Twitter速率限制异常。"""
        error = TwitterRateLimitError("API限制", retry_after=900.0)
        assert isinstance(error, RateLimitError)
        assert error.retry_after == 900.0
        
    def test_twitter_auth_error(self):
        """测试Twitter认证异常。"""
        error = TwitterAuthError("Token无效")
        assert isinstance(error, AuthError)

class TestBiliExceptions:
    """测试B站相关异常。"""
    
    def test_bili_basic_error(self):
        """测试B站基本异常。"""
        error = BiliError("视频不存在")
        assert error.platform == "bilibili"
        
    def test_bili_key_expired(self):
        """测试B站密钥过期异常。"""
        expired_time = datetime.now()
        error = BiliKeyExpiredError("WBI密钥过期", expired_at=expired_time)
        assert error.expired_at == expired_time
        assert expired_time.isoformat() in str(error)
        
    def test_bili_rate_limit(self):
        """测试B站速率限制异常。"""
        error = BiliRateLimitError("请求过于频繁", retry_after=60.0)
        assert isinstance(error, RateLimitError)
        assert error.retry_after == 60.0

class TestErrorFactory:
    """测试异常工厂函数。"""
    
    @pytest.mark.parametrize("platform,code,expected_type", [
        ("twitter", 429, TwitterRateLimitError),
        ("twitter", 401, TwitterAuthError),
        ("twitter", 404, ResourceNotFoundError),
        ("bilibili", -412, BiliRateLimitError),
        ("bilibili", -101, BiliKeyExpiredError),
        ("bilibili", -404, ResourceNotFoundError),
        ("unknown", 404, PlatformError),
    ])
    def test_create_platform_error(self, platform, code, expected_type):
        """测试异常工厂函数的错误码映射。"""
        error = create_platform_error(platform, code, "测试错误")
        assert isinstance(error, expected_type)
        assert error.platform == platform
        assert error.code == code

    def test_create_error_with_kwargs(self):
        """测试带额外参数的异常创建。"""
        error = create_platform_error(
            "bilibili",
            -101,
            "密钥过期",
            expired_at=datetime.now()
        )
        assert isinstance(error, BiliKeyExpiredError)
        assert hasattr(error, "expired_at")

class TestDownloadExceptions:
    """测试下载相关异常。"""
    
    def test_download_error(self):
        """测试基本下载错误。"""
        url = "https://example.com/video.mp4"
        error = DownloadError("test", "下载失败", url)
        assert error.platform == "test"
        assert error.url == url
        assert error.progress is None
        assert "下载失败" in str(error)
        
    def test_download_error_with_progress(self):
        """测试带进度的下载错误。"""
        url = "https://example.com/video.mp4"
        error = DownloadError("test", "下载失败", url, progress=45.5)
        assert error.progress == 45.5
        assert "progress=45.5%" in str(error)
        
    def test_download_canceled(self):
        """测试下载取消异常。"""
        url = "https://example.com/video.mp4"
        error = DownloadCanceled("test", url)
        assert isinstance(error, DownloadError)
        assert error.url == url
        assert "canceled" in str(error).lower()
        
    def test_download_canceled_with_progress(self):
        """测试带进度的下载取消异常。"""
        url = "https://example.com/video.mp4"
        error = DownloadCanceled("test", url, progress=75.8)
        assert error.progress == 75.8
        assert "progress=75.8%" in str(error)
        assert "canceled" in str(error).lower() 