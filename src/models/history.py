"""下载历史模型。

记录视频下载历史。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, Float, event
from sqlalchemy.sql import func
from sqlalchemy.orm import validates
from .base import Base

class DownloadHistory(Base):
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
    
    VALID_STATUSES = ('pending', 'downloading', 'success', 'failed')
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(500), nullable=False, index=True)
    title = Column(String(200))
    platform = Column(String(50), index=True)
    creator_id = Column(String(50), index=True)
    
    file_path = Column(String(500))
    file_size = Column(Float)  # MB
    duration = Column(Float)   # seconds
    
    status = Column(
        Enum(*VALID_STATUSES, name='download_status'),
        default='pending',
        nullable=False,
        index=True
    )
    error = Column(Text)
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    @validates('status')
    def validate_status(self, key, value):
        """验证状态值。"""
        if value not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {value}. Must be one of: {self.VALID_STATUSES}")
        return value
    
    def __repr__(self):
        """返回字符串表示。"""
        return f"<DownloadHistory(id={self.id}, url='{self.url}', status='{self.status}')>" 