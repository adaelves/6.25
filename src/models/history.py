"""下载历史模型。

记录视频下载历史。
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, DateTime, 
    Index, Text, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base
from .mixins import TimestampMixin

class DownloadHistory(Base, TimestampMixin):
    """下载历史记录。
    
    Attributes:
        id: 主键ID
        url: 视频URL
        title: 视频标题
        platform: 平台名称
        creator_id: 创作者ID
        file_path: 下载文件路径
        file_size: 文件大小(MB)
        duration: 视频时长(秒)
        status: 下载状态(pending/downloading/success/failed)
        error: 错误信息
        created_at: 创建时间
        updated_at: 更新时间
    """
    
    __tablename__ = 'download_history'
    
    # 索引配置
    __table_args__ = (
        # 创建者ID和下载日期联合索引
        Index('idx_creator_date', 'creator_id', 'created_at'),
        # 状态索引（用于统计）
        Index('idx_status', 'status'),
    )
    
    VALID_STATUSES = ('pending', 'downloading', 'success', 'failed')
    
    id = Column(Integer, primary_key=True)
    creator_id = Column(String(100), nullable=False, index=True)
    
    url = Column(String(500), nullable=False)
    title = Column(String(200))
    platform = Column(String(50), nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default='pending'
    )
    
    file_path = Column(Text)
    file_size = Column(BigInteger)
    duration = Column(Integer)  # 秒
    error = Column(Text)
    
    @property
    def is_successful(self) -> bool:
        """是否下载成功。"""
        return self.status == 'success'
    
    @property
    def has_error(self) -> bool:
        """是否有错误。"""
        return self.status == 'failed'
    
    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'platform': self.platform,
            'creator_id': self.creator_id,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'duration': self.duration,
            'status': self.status,
            'error_message': self.error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        """返回字符串表示。"""
        return f"<DownloadHistory(id={self.id}, url='{self.url}', status='{self.status}')>" 