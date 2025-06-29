"""创作者模型。"""

from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, 
    ForeignKey, Text, Boolean, BigInteger
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base
from .mixins import TimestampMixin

class Creator(Base, TimestampMixin):
    """创作者信息。"""
    
    __tablename__ = 'creators'
    
    # 主键
    id = Column(Integer, primary_key=True)
    
    # 基本信息
    platform = Column(String(50), nullable=False)
    platform_id = Column(String(100), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    avatar_url = Column(String(500))
    
    # 平台链接
    homepage_url = Column(String(500))
    social_links = Column(ARRAY(String))
    
    # 状态标记
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # 关联关系
    videos = relationship('Video', back_populates='creator')
    downloads = relationship('DownloadHistory', back_populates='creator')
    stats = relationship(
        'CreatorStats',
        back_populates='creator',
        uselist=False
    )
    
    def __repr__(self):
        return f"<Creator(id={self.id}, name='{self.name}', platform='{self.platform}')>"

class CreatorStats(Base, TimestampMixin):
    """创作者统计信息。"""
    
    __tablename__ = 'creator_stats'
    
    # 主键和关联
    id = Column(Integer, primary_key=True)
    creator_id = Column(
        Integer,
        ForeignKey('creators.id', ondelete='CASCADE'),
        nullable=False,
        unique=True
    )
    
    # 同步状态
    last_sync = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
    next_sync = Column(DateTime)
    sync_status = Column(
        String(20),
        nullable=False,
        default='pending'
    )
    sync_error = Column(Text)
    
    # 平台指标
    platform_metrics = Column(JSONB)
    
    # 视频统计
    total_videos = Column(Integer, default=0)
    downloaded_videos = Column(Integer, default=0)
    total_duration = Column(Integer, default=0)  # 秒
    total_size = Column(BigInteger, default=0)   # 字节
    
    # 错误统计
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    last_error_time = Column(DateTime)
    
    # 关联关系
    creator = relationship('Creator', back_populates='stats')
    
    @property
    def sync_age(self) -> Optional[float]:
        """获取同步年龄（小时）。"""
        if not self.last_sync:
            return None
        delta = datetime.now() - self.last_sync
        return delta.total_seconds() / 3600
        
    @property
    def needs_sync(self) -> bool:
        """是否需要同步。"""
        # 从未同步
        if not self.last_sync:
            return True
            
        # 有预定的下次同步时间
        if self.next_sync and datetime.now() >= self.next_sync:
            return True
            
        # 同步时间过久（默认24小时）
        if self.sync_age and self.sync_age >= 24:
            return True
            
        return False
        
    def update_metrics(self, metrics: Dict):
        """更新平台指标。
        
        Args:
            metrics: 平台指标数据
        """
        if not self.platform_metrics:
            self.platform_metrics = {}
            
        # 更新指标，保留历史数据
        self.platform_metrics.update(metrics)
        
    def record_error(self, error: Exception):
        """记录错误信息。
        
        Args:
            error: 异常对象
        """
        self.error_count += 1
        self.last_error = str(error)
        self.last_error_time = datetime.now()
        
    def update_video_stats(
        self,
        total: Optional[int] = None,
        downloaded: Optional[int] = None,
        duration: Optional[int] = None,
        size: Optional[int] = None
    ):
        """更新视频统计信息。
        
        Args:
            total: 总视频数
            downloaded: 已下载数
            duration: 总时长（秒）
            size: 总大小（字节）
        """
        if total is not None:
            self.total_videos = total
        if downloaded is not None:
            self.downloaded_videos = downloaded
        if duration is not None:
            self.total_duration = duration
        if size is not None:
            self.total_size = size
            
    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            'id': self.id,
            'creator_id': self.creator_id,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'next_sync': self.next_sync.isoformat() if self.next_sync else None,
            'sync_status': self.sync_status,
            'sync_error': self.sync_error,
            'platform_metrics': self.platform_metrics,
            'total_videos': self.total_videos,
            'downloaded_videos': self.downloaded_videos,
            'total_duration': self.total_duration,
            'total_size': self.total_size,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'last_error_time': self.last_error_time.isoformat() if self.last_error_time else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        } 