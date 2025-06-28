"""创作者数据模型。"""

from datetime import datetime
from typing import Dict, Any
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.sql import func

from .base import Base

class Creator(Base):
    """创作者数据模型。
    
    Attributes:
        id: 统一ID（由平台名和平台ID生成）
        name: 创作者名称
        avatar: 头像URL
        description: 简介
        platforms: 平台ID映射，格式：{platform: platform_id}
        extra_data: 附加元数据
        created_at: 创建时间
        updated_at: 更新时间
    """
    
    __tablename__ = 'creators'
    
    id = Column(String(32), primary_key=True)  # MD5长度
    name = Column(String(100), nullable=False)
    avatar = Column(String(500), nullable=True)
    description = Column(String(1000), nullable=True)
    platforms = Column(JSON, nullable=False, default=dict)  # {platform: platform_id}
    extra_data = Column(JSON, nullable=False, default=dict)  # 附加元数据
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self) -> str:
        return f"<Creator(id='{self.id}', name='{self.name}')>" 