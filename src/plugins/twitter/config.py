"""Twitter下载器配置模块。

该模块包含Twitter下载器的配置类。
"""

from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class TwitterDownloaderConfig:
    """Twitter下载器配置。
    
    Attributes:
        save_dir: 保存目录
        proxy: 代理地址
        timeout: 超时时间（秒）
        max_retries: 最大重试次数
        cookies_file: Cookie文件路径
        output_template: 输出文件名模板
        max_items: 最大下载数量
    """
    
    save_dir: Path = Path("downloads/twitter")
    proxy: Optional[str] = None
    timeout: int = 30
    max_retries: int = 5
    cookies_file: str = "config/twitter_cookies.txt"
    output_template: str = "%(uploader)s/%(upload_date)s-%(title)s-%(id)s.%(ext)s"
    max_items: Optional[int] = None
    
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
            "cookies_file": self.cookies_file,
            "output_template": self.output_template,
            "max_items": self.max_items,
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
        if self.cookies_file:
            opts['cookies'] = self.cookies_file
            
        return opts 