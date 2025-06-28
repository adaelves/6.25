"""视频数据模型。"""

from datetime import datetime
from typing import Dict, Any
from sqlalchemy import Column, String, DateTime, JSON, Float, ForeignKey, Index
from sqlalchemy.sql import func

from .base import Base

class Video(Base):
    """视频数据模型。
    
    Attributes:
        id: 主键ID
        creator_id: 创作者ID
        platform: 平台名称
        platform_id: 平台视频ID
        title: 标题
        description: 描述
        url: 视频URL
        thumbnail: 缩略图URL
        duration: 时长（秒）
        publish_time: 发布时间
        extra_data: 附加元数据
        created_at: 创建时间
        updated_at: 更新时间
        downloaded: 是否已下载
        file_path: 本地文件路径
        file_size: 文件大小(MB)
        file_md5: 文件MD5
    """
    
    __tablename__ = 'videos'
    
    id = Column(String(32), primary_key=True)  # MD5(platform:platform_id)
    creator_id = Column(String(32), ForeignKey('creators.id'), nullable=False)
    platform = Column(String(50), nullable=False)
    platform_id = Column(String(100), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(String(5000), nullable=True)
    url = Column(String(1000), nullable=False)
    thumbnail = Column(String(1000), nullable=True)
    duration = Column(Float, nullable=True)  # 秒
    publish_time = Column(DateTime, nullable=False)
    extra_data = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # 下载相关字段
    downloaded = Column(String(20), nullable=False, default='pending')  # pending, downloading, completed, failed
    file_path = Column(String(1000), nullable=True)
    file_size = Column(Float, nullable=True)  # MB
    file_md5 = Column(String(32), nullable=True, unique=True)
    
    # 索引
    __table_args__ = (
        Index('ix_videos_platform_id', 'platform', 'platform_id', unique=True),
        Index('ix_videos_creator_id', 'creator_id'),
        Index('ix_videos_publish_time', 'publish_time'),
        Index('ix_videos_downloaded', 'downloaded'),
    )
    
    def __repr__(self) -> str:
        return f"<Video(id='{self.id}', title='{self.title}')>" 