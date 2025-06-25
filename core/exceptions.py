"""核心异常模块。

定义了应用程序中使用的自定义异常类。
"""

class BiliBiliError(Exception):
    """B站API相关错误的基类。"""
    
    def __init__(self, message: str = None, code: int = None):
        """初始化异常。
        
        Args:
            message: 错误消息
            code: 错误代码
        """
        self.code = code
        super().__init__(message or self.default_message())
        
    def default_message(self) -> str:
        """默认错误消息。
        
        Returns:
            str: 错误消息
        """
        return "B站API调用出错"

class VIPContentError(BiliBiliError):
    """大会员专享内容错误。"""
    
    def default_message(self) -> str:
        return "该内容需要大会员权限。请登录大会员账号后重试，或选择其他视频观看。"

class RegionLockError(BiliBiliError):
    """地区限制错误。"""
    
    def default_message(self) -> str:
        return "该内容在当前地区不可用。您可以：\n1. 使用代理服务器（如香港、台湾节点）\n2. 选择其他可观看的视频"

class NetworkError(BiliBiliError):
    """网络请求错误。"""
    
    def default_message(self) -> str:
        return "网络请求失败，请检查网络连接或尝试使用代理服务器。"

class ParsingError(BiliBiliError):
    """内容解析错误。"""
    
    def default_message(self) -> str:
        return "视频信息解析失败，可能是接口变更或内容不存在。"

class RateLimitError(BiliBiliError):
    """请求频率限制错误。"""
    
    def default_message(self) -> str:
        return "请求过于频繁，请稍后再试或更换IP地址。" 