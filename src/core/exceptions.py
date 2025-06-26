"""异常处理模块。

定义了应用程序的异常体系，包括：
- 基础异常类
- 平台特定异常
- 网络异常
- 解析异常
- 认证异常
- 下载异常
"""

from typing import Optional, Dict, Any, Type, Union
from datetime import datetime

class PlatformError(Exception):
    """平台错误基类。
    
    所有平台相关的错误都应该继承此类。
    
    Attributes:
        platform: str, 平台标识
        msg: str, 错误消息
        code: Optional[int], 错误代码
        data: Optional[Dict[str, Any]], 附加数据
    """
    
    def __init__(
        self,
        platform: str,
        msg: str,
        code: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        """初始化平台错误。
        
        Args:
            platform: 平台标识（如 twitter、bilibili）
            msg: 错误消息
            code: 错误代码（可选）
            data: 附加数据（可选）
        """
        super().__init__(msg)
        self.platform = platform
        self.code = code
        self.data = data or {}
        self._set_message(f"[{platform}] {msg}")
        if code is not None:
            self._append_message(f"code={code}")
        
    def _set_message(self, msg: str) -> None:
        """设置错误消息。"""
        self.msg = msg
        
    def _append_message(self, info: str) -> None:
        """追加错误信息。"""
        self.msg = f"{self.msg} ({info})"
        
    def __str__(self) -> str:
        return self.msg

class NetworkError(PlatformError):
    """网络错误基类。
    
    用于表示网络请求相关的错误。
    
    Attributes:
        retry_after: Optional[float], 建议的重试等待时间（秒）
    """
    
    def __init__(
        self,
        platform: str,
        msg: str,
        retry_after: Optional[Union[float, int]] = None,
        **kwargs
    ):
        """初始化网络错误。
        
        Args:
            platform: 平台标识
            msg: 错误消息
            retry_after: 建议的重试等待时间（秒）
            **kwargs: 传递给父类的参数
        """
        super().__init__(platform, msg, **kwargs)
        self.retry_after = float(retry_after) if retry_after is not None else None
        if self.retry_after is not None:
            self._append_message(f"retry after {self.retry_after:.1f}s")

class RateLimitError(NetworkError):
    """速率限制错误基类。"""
    pass

class AuthError(PlatformError):
    """认证错误基类。"""
    pass

class ParseError(PlatformError):
    """解析错误基类。"""
    pass

class ResourceNotFoundError(PlatformError):
    """资源不存在错误。"""
    pass

# Twitter 相关异常
class TwitterError(PlatformError):
    """Twitter错误基类。"""
    
    def __init__(self, msg: str, code: Optional[int] = None, **kwargs):
        super().__init__("twitter", msg, code=code, **kwargs)

class TwitterRateLimitError(TwitterError, RateLimitError):
    """Twitter API 速率限制错误。"""
    
    def __init__(self, msg: str, retry_after: Optional[Union[float, int]] = None, code: Optional[int] = None, **kwargs):
        TwitterError.__init__(self, msg, code=code, **kwargs)
        self.retry_after = float(retry_after) if retry_after is not None else None
        if self.retry_after is not None:
            self._append_message(f"retry after {self.retry_after:.1f}s")

class TwitterAuthError(TwitterError, AuthError):
    """Twitter 认证错误。"""
    pass

class TwitterParseError(TwitterError, ParseError):
    """Twitter 数据解析错误。"""
    pass

# B站相关异常
class BiliError(PlatformError):
    """B站错误基类。"""
    
    def __init__(self, msg: str, code: Optional[int] = None, **kwargs):
        super().__init__("bilibili", msg, code=code, **kwargs)

class BiliRateLimitError(BiliError, RateLimitError):
    """B站 API 速率限制错误。"""
    
    def __init__(self, msg: str, retry_after: Optional[Union[float, int]] = None, code: Optional[int] = None, **kwargs):
        BiliError.__init__(self, msg, code=code, **kwargs)
        self.retry_after = float(retry_after) if retry_after is not None else None
        if self.retry_after is not None:
            self._append_message(f"retry after {self.retry_after:.1f}s")

class BiliKeyExpiredError(BiliError):
    """B站密钥过期错误。
    
    Attributes:
        expired_at: datetime, 过期时间
    """
    
    def __init__(
        self,
        msg: str,
        expired_at: Optional[datetime] = None,
        code: Optional[int] = None,
        **kwargs
    ):
        """初始化密钥过期错误。
        
        Args:
            msg: 错误消息
            expired_at: 过期时间
            code: 错误代码（可选）
            **kwargs: 传递给父类的参数
        """
        super().__init__(msg, code=code, **kwargs)
        self.expired_at = expired_at
        if expired_at is not None:
            self._append_message(f"expired at {expired_at.isoformat()}")

class BiliAuthError(BiliError, AuthError):
    """B站认证错误。"""
    pass

class BiliParseError(BiliError, ParseError):
    """B站数据解析错误。"""
    pass

# 下载相关异常
class DownloadError(PlatformError):
    """下载错误基类。
    
    用于表示下载过程中的通用错误。
    
    Attributes:
        url: str, 下载URL
        progress: Optional[float], 下载进度（0-100）
    """
    
    def __init__(
        self,
        platform: str,
        msg: str,
        url: str,
        progress: Optional[Union[float, int]] = None,
        **kwargs
    ):
        """初始化下载错误。
        
        Args:
            platform: 平台标识
            msg: 错误消息
            url: 下载URL
            progress: 下载进度（0-100）
            **kwargs: 传递给父类的参数
        """
        super().__init__(platform, msg, **kwargs)
        self.url = url
        self.progress = float(progress) if progress is not None else None
        if self.progress is not None:
            self._append_message(f"progress={self.progress:.1f}%")

class DownloadCanceled(DownloadError):
    """下载取消异常。
    
    用于表示用户主动取消下载。
    """
    
    def __init__(
        self,
        platform: str,
        url: str,
        progress: Optional[Union[float, int]] = None,
        **kwargs
    ):
        """初始化下载取消异常。
        
        Args:
            platform: 平台标识
            url: 下载URL
            progress: 下载进度（0-100）
            **kwargs: 传递给父类的参数
        """
        super().__init__(
            platform,
            "Download canceled by user",
            url,
            progress=progress,
            **kwargs
        )

# 通用错误
class ConfigError(Exception):
    """配置错误。"""
    pass

class ValidationError(Exception):
    """数据验证错误。"""
    pass

# 异常代码映射
ERROR_CODES: Dict[str, Dict[int, Type[PlatformError]]] = {
    # Twitter 错误码
    "twitter": {
        429: TwitterRateLimitError,
        401: TwitterAuthError,
        404: ResourceNotFoundError
    },
    # B站错误码
    "bilibili": {
        -412: BiliRateLimitError,
        -101: BiliKeyExpiredError,
        -404: ResourceNotFoundError
    }
}

def create_platform_error(
    platform: str,
    code: int,
    msg: str,
    **kwargs
) -> PlatformError:
    """根据平台和错误码创建对应的异常。
    
    Args:
        platform: 平台标识
        code: 错误码
        msg: 错误消息
        **kwargs: 传递给异常构造函数的参数
        
    Returns:
        PlatformError: 对应的平台异常实例
        
    Examples:
        >>> error = create_platform_error("twitter", 429, "Rate limited")
        >>> isinstance(error, TwitterRateLimitError)
        True
    """
    error_class = ERROR_CODES.get(platform, {}).get(code, PlatformError)
    
    # 处理平台特定的错误类
    if issubclass(error_class, (TwitterError, BiliError)):
        # 处理速率限制错误
        if issubclass(error_class, (TwitterRateLimitError, BiliRateLimitError)):
            return error_class(msg, code=code, **kwargs)
        # 处理认证错误
        if issubclass(error_class, (TwitterAuthError, BiliAuthError)):
            return error_class(msg, code=code, **kwargs)
        # 处理其他平台特定错误
        return error_class(msg, code=code, **kwargs)
    
    # 处理通用错误类
    return error_class(platform, msg, code=code, **kwargs)

class BiliBiliError(Exception):
    """哔哩哔哩相关错误的基类。"""
    pass

class NetworkError(BiliBiliError):
    """网络错误。"""
    pass

class APIError(BiliBiliError):
    """API错误。"""
    pass

class ExtractError(BiliBiliError):
    """提取错误。"""
    pass

class DownloadError(BiliBiliError):
    """下载错误。"""
    pass

class AuthError(BiliBiliError):
    """认证错误。"""
    pass 