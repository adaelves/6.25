"""媒体项数据模型。"""

from typing import Optional
from dataclasses import dataclass

@dataclass
class MediaItem:
    """媒体项数据模型。
    
    Attributes:
        url: 媒体URL
        title: 标题
        platform: 平台名称
        creator_id: 创作者ID
        file_path: 文件保存路径
        file_size: 文件大小(MB)
        duration: 媒体时长(秒)
    """
    
    url: str
    title: Optional[str] = None
    platform: Optional[str] = None
    creator_id: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[float] = None
    duration: Optional[float] = None 