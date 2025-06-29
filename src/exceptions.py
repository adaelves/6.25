"""异常定义。

定义项目中使用的自定义异常类。
"""

class BaseError(Exception):
    """基础异常类。"""
    pass

class NetworkError(BaseError):
    """网络错误。"""
    pass

class RateLimitError(NetworkError):
    """请求频率限制错误。"""
    pass

class LoginRequiredError(NetworkError):
    """需要登录错误。"""
    pass

class ContentExpiredError(NetworkError):
    """内容已过期错误。"""
    pass

class ExtractError(BaseError):
    """内容提取错误。"""
    pass

class VideoProcessError(BaseError):
    """视频处理错误。"""
    pass

class MetadataError(BaseError):
    """元数据处理错误。"""
    pass

class ProcessError(BaseError):
    """处理错误。"""
    pass

class AuthError(BaseError):
    """认证错误。"""
    pass 