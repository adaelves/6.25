"""视频扫描服务。

提供视频扫描和更新检测功能。
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Set
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib

from ..models.videos import Video
from ..models.creators import Creator
from ..schemas.video import VideoInfo, VideoUpdate
from .creator import CreatorManager

logger = logging.getLogger(__name__)

class VideoScanner:
    """视频扫描服务。
    
    提供视频扫描和更新检测功能。
    
    Attributes:
        engine: SQLAlchemy引擎实例
        creator_manager: 创作者管理服务实例
        executor: 线程池执行器
    """
    
    def __init__(
        self,
        db_url: str,
        creator_manager: CreatorManager,
        max_workers: int = 4
    ):
        """初始化视频扫描服务。
        
        Args:
            db_url: 数据库连接URL
            creator_manager: 创作者管理服务实例
            max_workers: 最大工作线程数
        """
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False}
        )
        self.creator_manager = creator_manager
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
    async def scan_creator_videos(
        self,
        platform: str,
        platform_id: str,
        since: Optional[datetime] = None
    ) -> List[VideoInfo]:
        """扫描创作者视频。
        
        Args:
            platform: 平台名称
            platform_id: 平台ID
            since: 起始时间（可选）
            
        Returns:
            List[VideoInfo]: 视频信息列表
        """
        try:
            # 获取创作者信息
            creator = self.creator_manager.get_creator(platform, platform_id)
            if not creator:
                logger.error(f"Creator not found: {platform}:{platform_id}")
                return []
                
            # 获取平台API
            api = self._get_platform_api(platform)
            
            # 异步获取视频列表
            videos = await api.get_creator_videos(platform_id, since)
            
            # 更新数据库
            return await self._update_videos(creator, videos)
            
        except Exception as e:
            logger.error(f"Failed to scan creator videos: {e}")
            return []
            
    async def scan_all_creators(
        self,
        platform: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, List[VideoInfo]]:
        """扫描所有创作者视频。
        
        Args:
            platform: 平台名称（可选）
            since: 起始时间（可选）
            
        Returns:
            Dict[str, List[VideoInfo]]: 按创作者ID分组的视频信息
        """
        try:
            with Session(self.engine) as session:
                # 查询创作者列表
                query = session.query(Creator)
                if platform:
                    query = query.filter(Creator.platforms[platform].isnot(None))
                creators = query.all()
                
            # 并发扫描所有创作者
            tasks = []
            for creator in creators:
                for platform_name, platform_id in creator.platforms.items():
                    if platform and platform != platform_name:
                        continue
                    task = self.scan_creator_videos(
                        platform_name,
                        platform_id,
                        since
                    )
                    tasks.append((creator.id, task))
                    
            # 等待所有任务完成
            results = {}
            for creator_id, task in tasks:
                try:
                    videos = await task
                    results[creator_id] = videos
                except Exception as e:
                    logger.error(f"Failed to scan creator {creator_id}: {e}")
                    results[creator_id] = []
                    
            return results
            
        except Exception as e:
            logger.error(f"Failed to scan all creators: {e}")
            return {}
            
    async def check_updates(
        self,
        interval: timedelta = timedelta(hours=1)
    ) -> Dict[str, List[VideoInfo]]:
        """检查视频更新。
        
        Args:
            interval: 检查间隔
            
        Returns:
            Dict[str, List[VideoInfo]]: 新增的视频信息
        """
        since = datetime.utcnow() - interval
        return await self.scan_all_creators(since=since)
        
    def get_pending_videos(
        self,
        platform: Optional[str] = None,
        limit: int = 100
    ) -> List[VideoInfo]:
        """获取待下载视频。
        
        Args:
            platform: 平台名称（可选）
            limit: 返回数量限制
            
        Returns:
            List[VideoInfo]: 待下载视频列表
        """
        try:
            with Session(self.engine) as session:
                query = session.query(Video).filter_by(downloaded='pending')
                if platform:
                    query = query.filter_by(platform=platform)
                videos = query.order_by(Video.publish_time.desc()).limit(limit).all()
                return [VideoInfo.from_orm(v) for v in videos]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get pending videos: {e}")
            return []
            
    def update_video_status(
        self,
        video_id: str,
        status: str,
        file_info: Optional[Dict[str, Any]] = None
    ) -> Optional[VideoInfo]:
        """更新视频状态。
        
        Args:
            video_id: 视频ID
            status: 新状态
            file_info: 文件信息（可选）
            
        Returns:
            Optional[VideoInfo]: 更新后的视频信息
        """
        try:
            with Session(self.engine) as session:
                video = session.query(Video).filter_by(id=video_id).first()
                if not video:
                    return None
                    
                # 更新状态
                video.downloaded = status
                
                # 更新文件信息
                if file_info:
                    video.file_path = file_info.get('path')
                    video.file_size = file_info.get('size')
                    video.file_md5 = file_info.get('md5')
                    
                session.commit()
                return VideoInfo.from_orm(video)
        except SQLAlchemyError as e:
            logger.error(f"Failed to update video status: {e}")
            return None
            
    async def _update_videos(
        self,
        creator: Creator,
        videos: List[Dict[str, Any]]
    ) -> List[VideoInfo]:
        """更新视频信息。
        
        Args:
            creator: 创作者记录
            videos: 视频信息列表
            
        Returns:
            List[VideoInfo]: 更新后的视频信息
        """
        try:
            with Session(self.engine) as session:
                results = []
                for video_data in videos:
                    # 生成视频ID
                    video_id = self._generate_video_id(
                        video_data["platform"],
                        video_data["id"]
                    )
                    
                    # 检查视频是否存在
                    video = session.query(Video).filter_by(id=video_id).first()
                    
                    if video:
                        # 更新现有记录
                        for key, value in video_data.items():
                            if hasattr(video, key):
                                setattr(video, key, value)
                    else:
                        # 创建新记录
                        video = Video(
                            id=video_id,
                            creator_id=creator.id,
                            platform=video_data["platform"],
                            platform_id=video_data["id"],
                            title=video_data["title"],
                            description=video_data.get("description"),
                            url=video_data["url"],
                            thumbnail=video_data.get("thumbnail"),
                            duration=video_data.get("duration"),
                            publish_time=video_data["publish_time"],
                            extra_data=video_data.get("metadata", {})
                        )
                        session.add(video)
                        
                    results.append(VideoInfo.from_orm(video))
                    
                session.commit()
                return results
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to update videos: {e}")
            return []
            
    def _generate_video_id(self, platform: str, platform_id: str) -> str:
        """生成视频ID。
        
        Args:
            platform: 平台名称
            platform_id: 平台视频ID
            
        Returns:
            str: 视频ID
        """
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