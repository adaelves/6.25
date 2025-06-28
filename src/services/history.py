"""下载历史记录服务。

提供下载历史的记录和查询功能。
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging

from ..models.history import DownloadHistory
from ..schemas.media import MediaItem

logger = logging.getLogger(__name__)

class HistoryService:
    """下载历史记录服务。
    
    提供下载历史的记录和查询功能。
    
    Attributes:
        engine: SQLAlchemy引擎实例
    """
    
    def __init__(self, db_url: str):
        """初始化历史记录服务。
        
        Args:
            db_url: 数据库连接URL
        """
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False}  # SQLite特定配置
        )
        
    def log_download(
        self,
        item: MediaItem,
        status: str = 'success',
        error: Optional[str] = None
    ) -> bool:
        """记录下载历史。
        
        Args:
            item: 媒体项
            status: 下载状态，默认为'success'
            error: 错误信息，可选
            
        Returns:
            bool: 是否记录成功
            
        Raises:
            ValueError: 当状态值无效时
        """
        try:
            with Session(self.engine) as session:
                history = DownloadHistory(
                    url=item.url,
                    title=item.title,
                    platform=item.platform,
                    creator_id=item.creator_id,
                    file_path=item.file_path,
                    file_size=item.file_size,
                    duration=item.duration,
                    status=status,
                    error=error
                )
                session.add(history)
                session.commit()
                return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to log download history: {e}")
            return False
            
    def get_recent(self, limit: int = 100) -> List[DownloadHistory]:
        """获取最近的下载记录。
        
        Args:
            limit: 返回记录数量限制，默认100条
            
        Returns:
            List[DownloadHistory]: 下载历史记录列表
        """
        try:
            with Session(self.engine) as session:
                return session.query(DownloadHistory).order_by(
                    DownloadHistory.created_at.desc()
                ).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get recent history: {e}")
            return []
            
    def get_by_status(
        self,
        status: str,
        limit: int = 100
    ) -> List[DownloadHistory]:
        """按状态获取下载记录。
        
        Args:
            status: 下载状态
            limit: 返回记录数量限制，默认100条
            
        Returns:
            List[DownloadHistory]: 下载历史记录列表
            
        Raises:
            ValueError: 当状态值无效时
        """
        try:
            with Session(self.engine) as session:
                return session.query(DownloadHistory).filter_by(
                    status=status
                ).order_by(
                    DownloadHistory.created_at.desc()
                ).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get history by status: {e}")
            return []
            
    def get_by_creator(
        self,
        creator_id: str,
        limit: int = 100
    ) -> List[DownloadHistory]:
        """获取指定创作者的下载记录。
        
        Args:
            creator_id: 创作者ID
            limit: 返回记录数量限制，默认100条
            
        Returns:
            List[DownloadHistory]: 下载历史记录列表
        """
        try:
            with Session(self.engine) as session:
                return session.query(DownloadHistory).filter_by(
                    creator_id=creator_id
                ).order_by(
                    DownloadHistory.created_at.desc()
                ).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Failed to get history by creator: {e}")
            return []
            
    def clear_history(self, days: int = 30) -> bool:
        """清理指定天数之前的历史记录。
        
        Args:
            days: 保留天数，默认30天
            
        Returns:
            bool: 是否清理成功
        """
        try:
            with Session(self.engine) as session:
                cutoff = datetime.utcnow() - timedelta(days=days)
                session.query(DownloadHistory).filter(
                    DownloadHistory.created_at < cutoff
                ).delete()
                session.commit()
                return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to clear history: {e}")
            return False 