"""数据库管理模块。

提供数据库连接和会话管理。
"""

import os
from typing import Optional, Type, TypeVar
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import logging
from datetime import datetime

from .models import Base, Video, Tag, Category, DownloadHistory

logger = logging.getLogger(__name__)

T = TypeVar('T')

class DatabaseManager:
    """数据库管理器。
    
    提供以下功能：
    - 数据库连接管理
    - 会话管理
    - 基本的CRUD操作
    - 错误处理和日志记录
    """
    
    def __init__(self, db_url: str):
        """初始化数据库管理器。
        
        Args:
            db_url: 数据库URL
        """
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        
    def init_db(self):
        """初始化数据库。
        
        创建所有表。
        """
        Base.metadata.create_all(self.engine)
        logger.info("数据库初始化完成")
        
    @contextmanager
    def session_scope(self):
        """提供事务作用域的会话上下文。
        
        用法:
            with db.session_scope() as session:
                session.add(some_object)
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {str(e)}")
            raise
        finally:
            session.close()
            
    def add(self, obj: T) -> Optional[T]:
        """添加对象到数据库。
        
        Args:
            obj: 要添加的对象
            
        Returns:
            Optional[T]: 添加的对象，如果失败返回None
        """
        try:
            with self.session_scope() as session:
                session.add(obj)
                session.flush()
                return obj
        except SQLAlchemyError as e:
            logger.error(f"添加对象失败: {str(e)}")
            return None
            
    def get(self, model: Type[T], id: int) -> Optional[T]:
        """根据ID获取对象。
        
        Args:
            model: 模型类
            id: 对象ID
            
        Returns:
            Optional[T]: 查找的对象，如果不存在返回None
        """
        try:
            with self.session_scope() as session:
                return session.query(model).get(id)
        except SQLAlchemyError as e:
            logger.error(f"获取对象失败: {str(e)}")
            return None
            
    def update(self, obj: T, **kwargs) -> bool:
        """更新对象。
        
        Args:
            obj: 要更新的对象
            **kwargs: 要更新的属性
            
        Returns:
            bool: 是否更新成功
        """
        try:
            with self.session_scope() as session:
                for key, value in kwargs.items():
                    setattr(obj, key, value)
                session.merge(obj)
                return True
        except SQLAlchemyError as e:
            logger.error(f"更新对象失败: {str(e)}")
            return False
            
    def delete(self, obj: T) -> bool:
        """删除对象。
        
        Args:
            obj: 要删除的对象
            
        Returns:
            bool: 是否删除成功
        """
        try:
            with self.session_scope() as session:
                session.delete(obj)
                return True
        except SQLAlchemyError as e:
            logger.error(f"删除对象失败: {str(e)}")
            return False
            
    def get_video_by_platform_id(self, platform: str, video_id: str) -> Optional[Video]:
        """根据平台和视频ID获取视频。
        
        Args:
            platform: 平台名称
            video_id: 平台视频ID
            
        Returns:
            Optional[Video]: 视频对象，如果不存在返回None
        """
        try:
            with self.session_scope() as session:
                return session.query(Video).filter_by(
                    platform=platform,
                    video_id=video_id
                ).first()
        except SQLAlchemyError as e:
            logger.error(f"获取视频失败: {str(e)}")
            return None
            
    def get_or_create_tag(self, name: str) -> Optional[Tag]:
        """获取或创建标签。
        
        Args:
            name: 标签名
            
        Returns:
            Optional[Tag]: 标签对象，如果失败返回None
        """
        try:
            with self.session_scope() as session:
                tag = session.query(Tag).filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name)
                    session.add(tag)
                    session.flush()
                return tag
        except SQLAlchemyError as e:
            logger.error(f"获取或创建标签失败: {str(e)}")
            return None
            
    def get_or_create_category(self, name: str, platform: str, parent_id: Optional[int] = None) -> Optional[Category]:
        """获取或创建分类。
        
        Args:
            name: 分类名
            platform: 平台名称
            parent_id: 父分类ID
            
        Returns:
            Optional[Category]: 分类对象，如果失败返回None
        """
        try:
            with self.session_scope() as session:
                category = session.query(Category).filter_by(
                    name=name,
                    platform=platform,
                    parent_id=parent_id
                ).first()
                if not category:
                    category = Category(
                        name=name,
                        platform=platform,
                        parent_id=parent_id
                    )
                    session.add(category)
                    session.flush()
                return category
        except SQLAlchemyError as e:
            logger.error(f"获取或创建分类失败: {str(e)}")
            return None
            
    def add_download_history(
        self,
        video: Video,
        status: str,
        file_path: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[DownloadHistory]:
        """添加下载历史。
        
        Args:
            video: 视频对象
            status: 下载状态
            file_path: 文件路径
            error_message: 错误信息
            
        Returns:
            Optional[DownloadHistory]: 下载历史对象，如果失败返回None
        """
        try:
            with self.session_scope() as session:
                history = DownloadHistory(
                    video_id=video.id,
                    start_time=datetime.now(),
                    status=status,
                    file_path=file_path,
                    error_message=error_message
                )
                session.add(history)
                session.flush()
                return history
        except SQLAlchemyError as e:
            logger.error(f"添加下载历史失败: {str(e)}")
            return None 