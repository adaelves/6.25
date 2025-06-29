"""Instagram内容提取器。

提供Instagram视频、图片和故事的下载功能。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import os
import re
from pathlib import Path

from ..utils.network import NetworkSession
from ..utils.video import VideoProcessor
from ..utils.metadata import MetadataCleaner
from ..exceptions import (
    ExtractError,
    LoginRequiredError,
    ContentExpiredError,
    RateLimitError
)

logger = logging.getLogger(__name__)

@dataclass
class StoryMetadata:
    """故事元数据。
    
    Attributes:
        story_id: 故事ID
        user_id: 用户ID
        username: 用户名
        media_type: 媒体类型(photo/video)
        url: 媒体URL
        thumbnail_url: 缩略图URL
        created_at: 创建时间
        expires_at: 过期时间
        taken_at: 拍摄时间
        width: 宽度
        height: 高度
        duration: 视频时长(秒)
    """
    
    story_id: str
    user_id: str
    username: str
    media_type: str
    url: str
    thumbnail_url: Optional[str] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    taken_at: Optional[datetime] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None

class InstagramExtractor:
    """Instagram内容提取器。
    
    提供以下功能：
    1. 故事下载和元数据获取
    2. 24小时过期处理
    3. 元数据清理
    4. 视频预处理
    
    Attributes:
        session: 网络会话
        video_processor: 视频处理器
        metadata_cleaner: 元数据清理器
    """
    
    # API端点
    API_BASE = "https://i.instagram.com/api/v1"
    STORY_INFO_URL = f"{API_BASE}/stories/{{user_id}}/reel/media/"
    STORY_DOWNLOAD_URL = f"{API_BASE}/media/{{story_id}}/info/"
    
    # 预处理器映射
    PREPROCESSORS = {
        'remove_metadata': 'clean_metadata',
        'compress_1080p': 'compress_to_1080p'
    }
    
    def __init__(
        self,
        session: Optional[NetworkSession] = None,
        video_processor: Optional[VideoProcessor] = None,
        metadata_cleaner: Optional[MetadataCleaner] = None
    ):
        """初始化提取器。
        
        Args:
            session: 网络会话，可选
            video_processor: 视频处理器，可选
            metadata_cleaner: 元数据清理器，可选
        """
        self.session = session or NetworkSession()
        self.video_processor = video_processor or VideoProcessor()
        self.metadata_cleaner = metadata_cleaner or MetadataCleaner()
        
    def download_story(
        self,
        story_id: str,
        output_dir: str = "downloads",
        preprocessors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """下载Instagram故事。
        
        Args:
            story_id: 故事ID
            output_dir: 输出目录
            preprocessors: 预处理器列表，可选
            
        Returns:
            Dict[str, Any]: 下载结果，包含以下字段：
                - url: 媒体URL
                - file_path: 保存路径
                - expires_at: 过期时间
                - metadata: 元数据
                
        Raises:
            LoginRequiredError: 需要登录
            ContentExpiredError: 内容已过期
            RateLimitError: 请求频率限制
            ExtractError: 提取失败
        """
        try:
            # 获取故事元数据
            metadata = self._get_story_metadata(story_id)
            
            # 检查是否过期
            if metadata.expires_at and metadata.expires_at < datetime.now():
                raise ContentExpiredError(
                    f"Story {story_id} has expired at {metadata.expires_at}"
                )
            
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 下载媒体文件
            file_path = self._download_media(
                metadata.url,
                output_dir,
                f"{story_id}.{self._get_extension(metadata)}"
            )
            
            # 应用预处理器
            if preprocessors:
                file_path = self._apply_preprocessors(
                    file_path,
                    preprocessors
                )
            
            return {
                'url': metadata.url,
                'file_path': file_path,
                'expires_at': metadata.expires_at,
                'metadata': metadata.__dict__
            }
            
        except Exception as e:
            logger.error(f"Failed to download story {story_id}: {e}")
            if isinstance(e, (LoginRequiredError, ContentExpiredError, RateLimitError)):
                raise
            raise ExtractError(f"Failed to download story: {e}")
    
    def _get_story_metadata(self, story_id: str) -> StoryMetadata:
        """获取故事元数据。"""
        try:
            # 获取故事信息
            response = self.session.get(
                self.STORY_DOWNLOAD_URL.format(story_id=story_id)
            )
            data = response.json()
            
            if 'items' not in data or not data['items']:
                raise ExtractError(f"No items found for story {story_id}")
                
            item = data['items'][0]
            
            # 提取元数据
            metadata = StoryMetadata(
                story_id=story_id,
                user_id=str(item['user']['pk']),
                username=item['user']['username'],
                media_type='video' if item.get('video_duration') else 'photo',
                url=item.get('video_versions', [{'url': item['image_versions2']['candidates'][0]['url']}])[0]['url'],
                thumbnail_url=item['image_versions2']['candidates'][0]['url'],
                created_at=datetime.fromtimestamp(item['taken_at']),
                expires_at=datetime.fromtimestamp(item['expiring_at']),
                taken_at=datetime.fromtimestamp(item['taken_at']),
                width=item['original_width'],
                height=item['original_height'],
                duration=item.get('video_duration')
            )
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get story metadata: {e}")
            if isinstance(e, (LoginRequiredError, RateLimitError)):
                raise
            raise ExtractError(f"Failed to get story metadata: {e}")
    
    def _download_media(
        self,
        url: str,
        output_dir: str,
        filename: str
    ) -> str:
        """下载媒体文件。"""
        try:
            file_path = os.path.join(output_dir, filename)
            
            # 下载文件
            response = self.session.get(url, stream=True)
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to download media: {e}")
            raise ExtractError(f"Failed to download media: {e}")
    
    def _apply_preprocessors(
        self,
        file_path: str,
        preprocessors: List[str]
    ) -> str:
        """应用预处理器。"""
        current_path = file_path
        
        try:
            for preprocessor in preprocessors:
                if preprocessor not in self.PREPROCESSORS:
                    logger.warning(f"Unknown preprocessor: {preprocessor}")
                    continue
                    
                # 获取处理器方法
                processor_method = getattr(
                    self,
                    self.PREPROCESSORS[preprocessor]
                )
                
                # 应用处理器
                result_path = processor_method(current_path)
                if result_path != current_path:
                    if os.path.exists(current_path):
                        os.remove(current_path)
                    current_path = result_path
                    
            return current_path
            
        except Exception as e:
            logger.error(f"Failed to apply preprocessors: {e}")
            raise ExtractError(f"Failed to apply preprocessors: {e}")
    
    def clean_metadata(self, file_path: str) -> str:
        """清理元数据。"""
        return self.metadata_cleaner.clean(file_path)
        
    def compress_to_1080p(self, file_path: str) -> str:
        """压缩到1080p。"""
        return self.video_processor.compress_to_1080p(file_path)
        
    def _get_extension(self, metadata: StoryMetadata) -> str:
        """获取文件扩展名。"""
        if metadata.media_type == 'video':
            return 'mp4'
        return 'jpg' 