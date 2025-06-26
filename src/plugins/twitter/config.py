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
        filename_template: 文件名模板
        max_concurrent_downloads: 最大并发下载数
        speed_limit: 速度限制(bytes/s)
        chunk_size: 分块大小(bytes)
        max_retries: 最大重试次数
        proxy: 代理服务器
        timeout: 超时时间(秒)
        api_token: API令牌
        custom_headers: 自定义请求头
    """
    
    save_dir: Path
    filename_template: str = "{author}/{tweet_id}/{media_type}_{index}{ext}"
    max_concurrent_downloads: int = 3
    speed_limit: int = 0  # 0表示不限速
    chunk_size: int = 8192
    max_retries: int = 3
    proxy: Optional[str] = None
    timeout: float = 30.0
    api_token: str = ""
    custom_headers: Dict[str, str] = field(default_factory=dict)
    
    # 文件名模板变量说明
    TEMPLATE_VARS = {
        "author": "作者用户名",
        "tweet_id": "推文ID",
        "media_type": "媒体类型(photo/video)",
        "index": "媒体索引(从1开始)",
        "timestamp": "发布时间戳",
        "date": "发布日期(YYYY-MM-DD)",
        "time": "发布时间(HH-MM-SS)",
        "likes": "点赞数",
        "reposts": "转发数",
        "quality": "媒体质量",
        "ext": "文件扩展名"
    }
    
    def __post_init__(self):
        """初始化后处理。"""
        if isinstance(self.save_dir, str):
            self.save_dir = Path(self.save_dir)
            
        # 设置默认请求头
        if not self.custom_headers:
            self.custom_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://twitter.com/",
                "Origin": "https://twitter.com"
            }
            
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "save_dir": str(self.save_dir),
            "filename_template": self.filename_template,
            "max_concurrent_downloads": self.max_concurrent_downloads,
            "speed_limit": self.speed_limit,
            "chunk_size": self.chunk_size,
            "max_retries": self.max_retries,
            "proxy": self.proxy,
            "timeout": self.timeout
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