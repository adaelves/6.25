"""异常类模块。

定义项目中使用的所有异常类。
"""

class BiliBiliError(Exception):
    """B站相关错误的基类。"""
    pass

class VIPContentError(BiliBiliError):
    """大会员专享内容错误。"""
    pass

class RegionLockError(BiliBiliError):
    """地区限制错误。"""
    pass

class NetworkError(BiliBiliError):
    """网络错误。"""
    pass

class ParsingError(BiliBiliError):
    """解析错误。"""
    pass

class RateLimitError(BiliBiliError):
    """请求频率限制错误。"""
    pass

class DownloadCanceled(Exception):
    """下载已取消。"""
    pass

class DanmakuError(BiliBiliError):
    """弹幕处理错误。"""
    pass

class DownloadError(Exception):
    """下载错误。"""
    pass 