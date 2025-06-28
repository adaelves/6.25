"""创作者管理服务。

提供创作者信息的同步和管理功能。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
import hashlib

from ..models.creators import Creator
from ..schemas.creator import CreatorUpdate

logger = logging.getLogger(__name__)

class CreatorManager:
    """创作者管理服务。
    
    提供创作者信息的同步和管理功能。
    
    Attributes:
        engine: SQLAlchemy引擎实例
    """
    
    def __init__(self, db_url: str):
        """初始化创作者管理服务。
        
        Args:
            db_url: 数据库连接URL
        """
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False}  # SQLite特定配置
        )
        
    def sync_creators(self, platform: str) -> bool:
        """从指定平台同步创作者数据。
        
        Args:
            platform: 平台名称
            
        Returns:
            bool: 是否同步成功
        """
        try:
            api = self._get_platform_api(platform)
            creators = api.get_followed_creators()
            
            for creator_data in creators:
                self._update_or_create(
                    platform_id=creator_data.id,
                    platform=platform,
                    name=creator_data.name,
                    avatar=creator_data.avatar_url,
                    description=creator_data.description,
                    extra_data=creator_data.metadata
                )
            return True
        except Exception as e:
            logger.error(f"Failed to sync creators from {platform}: {e}")
            return False
            
    def _update_or_create(
        self,
        platform_id: str,
        platform: str,
        name: str,
        avatar: Optional[str] = None,
        description: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Creator]:
        """更新或创建创作者记录。
        
        Args:
            platform_id: 平台ID
            platform: 平台名称
            name: 创作者名称
            avatar: 头像URL
            description: 简介
            extra_data: 附加元数据
            
        Returns:
            Optional[Creator]: 创建或更新的创作者记录
        """
        try:
            with Session(self.engine) as session:
                # 生成统一ID
                unified_id = self._generate_unified_id(platform, platform_id)
                
                # 查找现有记录
                creator = session.query(Creator).filter_by(id=unified_id).first()
                
                if creator:
                    # 更新现有记录
                    creator.name = name
                    creator.avatar = avatar or creator.avatar
                    creator.description = description or creator.description
                    if extra_data:
                        creator.extra_data.update(extra_data)
                    creator.platforms[platform] = platform_id
                else:
                    # 创建新记录
                    creator = Creator(
                        id=unified_id,
                        name=name,
                        avatar=avatar,
                        description=description,
                        platforms={platform: platform_id},
                        extra_data=extra_data or {}
                    )
                    session.add(creator)
                
                session.commit()
                return creator
        except SQLAlchemyError as e:
            logger.error(f"Failed to update/create creator: {e}")
            return None
            
    def get_creator(self, platform: str, platform_id: str) -> Optional[Creator]:
        """获取创作者信息。
        
        Args:
            platform: 平台名称
            platform_id: 平台ID
            
        Returns:
            Optional[Creator]: 创作者记录
        """
        try:
            with Session(self.engine) as session:
                unified_id = self._generate_unified_id(platform, platform_id)
                return session.query(Creator).filter_by(id=unified_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get creator: {e}")
            return None
            
    def search_creators(
        self,
        keyword: str,
        platform: Optional[str] = None,
        limit: int = 100
    ) -> List[Creator]:
        """搜索创作者。
        
        Args:
            keyword: 搜索关键词
            platform: 平台名称（可选）
            limit: 返回数量限制
            
        Returns:
            List[Creator]: 创作者列表
        """
        try:
            with Session(self.engine) as session:
                query = session.query(Creator)
                
                # 构建搜索条件
                search_conditions = [
                    Creator.name.ilike(f"%{keyword}%"),
                    Creator.description.ilike(f"%{keyword}%")
                ]
                
                # 如果指定了平台，添加平台过滤
                if platform:
                    query = query.filter(Creator.platforms[platform].isnot(None))
                
                return query.filter(or_(*search_conditions)).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Failed to search creators: {e}")
            return []
            
    def update_creator(
        self,
        platform: str,
        platform_id: str,
        update_data: CreatorUpdate
    ) -> Optional[Creator]:
        """更新创作者信息。
        
        Args:
            platform: 平台名称
            platform_id: 平台ID
            update_data: 更新数据
            
        Returns:
            Optional[Creator]: 更新后的创作者记录
        """
        try:
            with Session(self.engine) as session:
                unified_id = self._generate_unified_id(platform, platform_id)
                creator = session.query(Creator).filter_by(id=unified_id).first()
                
                if not creator:
                    return None
                    
                # 更新字段
                for field, value in update_data.dict(exclude_unset=True).items():
                    if value is not None:
                        setattr(creator, field, value)
                        
                session.commit()
                return creator
        except SQLAlchemyError as e:
            logger.error(f"Failed to update creator: {e}")
            return None
            
    def delete_creator(self, platform: str, platform_id: str) -> bool:
        """删除创作者记录。
        
        Args:
            platform: 平台名称
            platform_id: 平台ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            with Session(self.engine) as session:
                unified_id = self._generate_unified_id(platform, platform_id)
                creator = session.query(Creator).filter_by(id=unified_id).first()
                
                if creator:
                    session.delete(creator)
                    session.commit()
                    return True
                return False
        except SQLAlchemyError as e:
            logger.error(f"Failed to delete creator: {e}")
            return False
            
    def _generate_unified_id(self, platform: str, platform_id: str) -> str:
        """生成统一ID。
        
        使用平台名称和平台ID生成统一的ID。
        
        Args:
            platform: 平台名称
            platform_id: 平台ID
            
        Returns:
            str: 统一ID
        """
        # 使用MD5生成统一ID
        content = f"{platform}:{platform_id}".encode('utf-8')
        return hashlib.md5(content).hexdigest()
        
    def _get_platform_api(self, platform: str) -> Any:
        """获取平台API实例。
        
        Args:
            platform: 平台名称
            
        Returns:
            Any: 平台API实例
            
        Raises:
            ValueError: 当平台不支持时
        """
        # TODO: 实现平台API工厂
        raise NotImplementedError("Platform API factory not implemented") 