"""Twitter下载器配置模块。

提供Twitter下载器的配置选项。
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class TwitterDownloaderConfig:
    """Twitter下载器配置。
    
    Attributes:
        save_dir: 保存目录
        proxy: 代理地址
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
        chunk_size: 分块大小(字节)
        max_concurrent_downloads: 最大并发下载数
        speed_limit: 速度限制(bytes/s)
        custom_headers: 自定义请求头
    """
    
    save_dir: Path
    proxy: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    chunk_size: int = 1024 * 1024  # 1MB
    max_concurrent_downloads: int = 3
    speed_limit: Optional[int] = None
    custom_headers: Dict[str, str] = None
    
    def __post_init__(self):
        """初始化后处理。"""
        if isinstance(self.save_dir, str):
            self.save_dir = Path(self.save_dir)
            
        if self.custom_headers is None:
            self.custom_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "save_dir": str(self.save_dir),
            "proxy": self.proxy,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "chunk_size": self.chunk_size,
            "max_concurrent_downloads": self.max_concurrent_downloads,
            "speed_limit": self.speed_limit
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