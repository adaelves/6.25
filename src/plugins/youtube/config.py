"""YouTube下载器配置模块。

该模块提供YouTube下载器的配置选项。
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class YouTubeDownloaderConfig:
    """YouTube下载器配置。
    
    Attributes:
        save_dir: 保存目录
        proxy: 代理地址
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
        chunk_size: 分块大小(字节)
        max_concurrent_downloads: 最大并发下载数
        speed_limit: 速度限制(bytes/s)
        custom_headers: 自定义请求头
        max_height: 最大视频高度
        prefer_quality: 优先选择的视频质量
        merge_output_format: 合并后的输出格式
    """
    
    save_dir: Path = Path("downloads")
    proxy: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    chunk_size: int = 8192
    max_concurrent_downloads: int = 3
    speed_limit: Optional[int] = None
    custom_headers: Dict[str, str] = field(default_factory=lambda: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    max_height: int = 1080
    prefer_quality: str = "1080p"
    merge_output_format: str = "mp4"
    
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
            "chunk_size": self.chunk_size,
            "max_concurrent_downloads": self.max_concurrent_downloads,
            "speed_limit": self.speed_limit,
            "max_height": self.max_height,
            "prefer_quality": self.prefer_quality,
            "merge_output_format": self.merge_output_format
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "YouTubeDownloaderConfig":
        """从字典创建配置。"""
        return cls(**data) 