"""数据模型模块"""

from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime

@dataclass
class CreatorInfo:
    """创作者信息"""
    id: str
    name: str
    platform: str
    avatar_url: Optional[str] = None
    description: Optional[str] = None

@dataclass
class VideoInfo:
    """视频信息"""
    id: str
    title: str
    description: str
    creator: CreatorInfo
    duration: int  # 视频时长(秒)
    publish_time: datetime
    thumbnail_url: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None

@dataclass
class DownloadHistory:
    """下载历史记录"""
    video: VideoInfo
    download_time: datetime
    save_path: str
    file_size: int
    duration: int  # 下载用时(秒)

@dataclass
class AppSettings:
    """应用程序设置"""
    download_path: str
    max_concurrent: int = 3
    theme_mode: str = "auto"
    font_scale: float = 1.0
    proxy_enabled: bool = False
    proxy_address: Optional[str] = None
    creator_monitor: List[CreatorInfo] = None
    
    def __post_init__(self):
        if self.creator_monitor is None:
            self.creator_monitor = [] 