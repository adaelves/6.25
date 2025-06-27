"""Twitter下载器配置模块。

该模块包含Twitter下载器的配置类。
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class TwitterDownloaderConfig:
    """Twitter下载器配置类。
    
    Attributes:
        save_dir: 保存目录
        proxy: 代理设置
        timeout: 超时设置（秒）
        max_retries: 最大重试次数
        cookies: cookies字典
        username: Twitter用户名
        password: Twitter密码
        browser_profile: 浏览器配置文件路径
        browser_path: 浏览器数据目录路径
    """
    
    save_dir: Path = Path("downloads")
    proxy: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    cookies: Dict[str, Any] = field(default_factory=dict)
    username: Optional[str] = None
    password: Optional[str] = None
    browser_profile: Optional[str] = None  # 例如 "chrome"
    browser_path: Optional[str] = None  # 浏览器数据目录路径
    
    def __post_init__(self):
        """初始化后处理。"""
        if isinstance(self.save_dir, str):
            self.save_dir = Path(self.save_dir)
            
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "save_dir": str(self.save_dir),
            "proxy": self.proxy,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "cookies": self.cookies,
            "username": self.username,
            "password": self.password,
            "browser_profile": self.browser_profile,
            "browser_path": self.browser_path
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TwitterDownloaderConfig":
        """从字典创建配置。"""
        return cls(**data)
        
    def validate_template(self, template: str) -> bool:
        """验证文件名模板。
        
        Args:
            template: 文件名模板
            
        Returns:
            bool: 是否有效
        """
        valid_vars = {
            "author", "tweet_id", "media_type", "index",
            "timestamp", "date", "time", "likes", "reposts",
            "quality", "ext"
        }
        
        try:
            # 提取模板中的变量
            vars_in_template = {
                var.split("}")[0]
                for var in template.split("{")[1:]
            }
            
            # 检查是否都是有效变量
            return all(var in valid_vars for var in vars_in_template)
            
        except Exception:
            return False

    def to_ydl_opts(self) -> Dict[str, Any]:
        """转换为yt-dlp选项。
        
        Returns:
            Dict[str, Any]: yt-dlp选项字典
        """
        opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'retries': self.max_retries,
            'socket_timeout': self.timeout,
        }
        
        if self.proxy:
            opts['proxy'] = self.proxy
            
        # 添加认证信息
        if self.cookies:
            opts['cookies'] = self.cookies
        elif self.username and self.password:
            opts['username'] = self.username
            opts['password'] = self.password
        elif self.browser_profile:
            if self.browser_path:
                # 如果指定了浏览器路径，使用 (browser_name, browser_path) 元组
                opts['cookiesfrombrowser'] = (
                    self.browser_profile,
                    self.browser_path
                )
            else:
                opts['cookiesfrombrowser'] = (self.browser_profile,)
            
        return opts 