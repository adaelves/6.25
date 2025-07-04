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
class DownloadError(Exception):
    """下载错误异常。
    
    Attributes:
        message: str, 错误消息
        error_type: str, 错误类型
        suggestion: str, 建议操作
        details: Dict[str, Any], 详细信息
    """
    
    def __init__(
        self,
        message: str,
        error_type: str = "unknown",
        suggestion: str = "",
        details: Optional[Dict[str, Any]] = None
    ):
        """初始化下载错误。
        
        Args:
            message: 错误消息
            error_type: 错误类型，默认为"unknown"
            suggestion: 建议操作，默认为空字符串
            details: 详细信息，默认为None
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.suggestion = suggestion
        self.details = details or {}
        
    def __str__(self) -> str:
        """返回错误描述。
        
        Returns:
            str: 格式化的错误描述
        """
        parts = [self.message]
        if self.suggestion:
            parts.append(f"建议: {self.suggestion}")
        if self.details:
            parts.append("详细信息:")
            for key, value in self.details.items():
                parts.append(f"  {key}: {value}")
        return "\n".join(parts)

class DownloadCanceled(DownloadError):
    """下载取消异常。
    
    用于表示用户主动取消下载。
    """
    
    def __init__(self, message: str = "下载已取消"):
        """初始化下载取消异常。
        
        Args:
            message: 错误消息，默认为"下载已取消"
        """
        super().__init__(
            message=message,
            error_type="canceled",
            suggestion="这是用户主动取消的结果，不需要任何操作"
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

class RateLimitException(Exception):
    """限流异常。
    
    当API请求触发限流时抛出。
    """
    pass

class AgeRestrictedError(PlatformError):
    """年龄限制错误。
    
    当访问需要年龄验证的内容时抛出。
    
    Attributes:
        min_age: Optional[int], 最小年龄要求
    """
    
    def __init__(
        self,
        platform: str,
        msg: str,
        min_age: Optional[int] = None,
        **kwargs
    ):
        """初始化年龄限制错误。
        
        Args:
            platform: 平台标识
            msg: 错误消息
            min_age: 最小年龄要求（可选）
            **kwargs: 传递给父类的参数
        """
        super().__init__(platform, msg, **kwargs)
        self.min_age = min_age
        if min_age is not None:
            self._append_message(f"minimum age={min_age}")

# YouTube 相关异常
class YouTubeError(PlatformError):
    """YouTube错误基类。"""
    
    def __init__(self, msg: str, code: Optional[int] = None, **kwargs):
        super().__init__("youtube", msg, code=code, **kwargs)

class YouTubeAgeRestrictedError(YouTubeError, AgeRestrictedError):
    """YouTube年龄限制错误。"""
    
    def __init__(self, msg: str, min_age: Optional[int] = None, code: Optional[int] = None, **kwargs):
        YouTubeError.__init__(self, msg, code=code, **kwargs)
        self.min_age = min_age
        if min_age is not None:
            self._append_message(f"minimum age={min_age}")

class DownloaderError(Exception):
    """下载器基础异常。"""
    
    def __init__(self, message: str, code: str = "E000"):
        """初始化异常。
        
        Args:
            message: 错误信息
            code: 错误代码
        """
        self.message = message
        self.code = code
        super().__init__(f"[{code}] {message}")

class NetworkError(DownloaderError):
    """网络错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E001")

class AuthError(DownloaderError):
    """认证错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E002")

class ParseError(DownloaderError):
    """解析错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E003")

class DownloadError(DownloaderError):
    """下载错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E004")

class ConfigError(DownloaderError):
    """配置错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E005")

class CacheError(DownloaderError):
    """缓存错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E006")

class CookieError(DownloaderError):
    """Cookie错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E007")

class FileError(DownloaderError):
    """文件错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E008")

class ValidationError(DownloaderError):
    """验证错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E009")

class NotFoundError(DownloaderError):
    """资源不存在错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E010")

class PermissionError(DownloaderError):
    """权限错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E011")

class TimeoutError(DownloaderError):
    """超时错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E012")

class RetryError(DownloaderError):
    """重试错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E013")

class ConcurrencyError(DownloaderError):
    """并发错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E014")

class MemoryError(DownloaderError):
    """内存错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E015")

class DiskError(DownloaderError):
    """磁盘错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E016")

class SignatureError(DownloaderError):
    """签名错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E017")

class FormatError(DownloaderError):
    """格式错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E018")

class UnsupportedError(DownloaderError):
    """不支持错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E019")

class AbortError(DownloaderError):
    """中止错误。"""
    
    def __init__(self, message: str):
        """初始化异常。
        
        Args:
            message: 错误信息
        """
        super().__init__(message, "E020") 