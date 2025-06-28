"""下载服务。

提供视频下载和管理功能。
"""

import os
import asyncio
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
import logging

from ..models.videos import Video
from ..schemas.video import VideoInfo
from .scanner import VideoScanner

logger = logging.getLogger(__name__)

class VideoDownloader:
    """视频下载服务。
    
    提供视频下载和管理功能。
    
    Attributes:
        scanner: 视频扫描服务实例
        download_dir: 下载目录
        max_workers: 最大工作线程数
        executor: 线程池执行器
    """
    
    def __init__(
        self,
        scanner: VideoScanner,
        download_dir: str,
        max_workers: int = 4
    ):
        """初始化下载服务。
        
        Args:
            scanner: 视频扫描服务实例
            download_dir: 下载目录
            max_workers: 最大工作线程数
        """
        self.scanner = scanner
        self.download_dir = download_dir
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # 确保下载目录存在
        os.makedirs(download_dir, exist_ok=True)
        
    async def start_auto_download(
        self,
        platform: Optional[str] = None,
        batch_size: int = 10,
        interval: int = 300  # 5分钟
    ):
        """启动自动下载。
        
        Args:
            platform: 平台名称（可选）
            batch_size: 每批下载数量
            interval: 检查间隔（秒）
        """
        while True:
            try:
                # 获取待下载视频
                videos = self.scanner.get_pending_videos(
                    platform=platform,
                    limit=batch_size
                )
                
                if videos:
                    # 并发下载视频
                    tasks = []
                    for video in videos:
                        task = self.download_video(video)
                        tasks.append(task)
                    
                    # 等待当前批次完成
                    await asyncio.gather(*tasks)
                    
                # 等待下一次检查
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Auto download error: {e}")
                await asyncio.sleep(interval)
                
    async def download_video(self, video: VideoInfo) -> bool:
        """下载单个视频。
        
        Args:
            video: 视频信息
            
        Returns:
            bool: 是否下载成功
        """
        try:
            # 更新状态为下载中
            self.scanner.update_video_status(video.id, "downloading")
            
            # 获取平台API
            api = self._get_platform_api(video.platform)
            
            # 准备下载路径
            file_path = self._generate_file_path(video)
            
            # 开始下载
            downloader = api.get_downloader(video.url)
            await downloader.download(file_path)
            
            # 计算文件信息
            file_info = await self._get_file_info(file_path)
            
            # 检查文件MD5是否重复
            if self._is_duplicate_file(file_info["md5"]):
                # 删除重复文件
                os.remove(file_path)
                self.scanner.update_video_status(video.id, "duplicate")
                return False
                
            # 更新状态为完成
            self.scanner.update_video_status(
                video.id,
                "completed",
                file_info
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to download video {video.id}: {e}")
            # 更新状态为失败
            self.scanner.update_video_status(video.id, "failed")
            return False
            
    def _generate_file_path(self, video: VideoInfo) -> str:
        """生成文件保存路径。
        
        Args:
            video: 视频信息
            
        Returns:
            str: 文件路径
        """
        # 创建平台子目录
        platform_dir = os.path.join(self.download_dir, video.platform)
        os.makedirs(platform_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{video.platform_id}_{timestamp}.mp4"
        
        return os.path.join(platform_dir, filename)
        
    async def _get_file_info(self, file_path: str) -> Dict[str, Any]:
        """获取文件信息。
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict[str, Any]: 文件信息
        """
        # 在线程池中执行IO操作
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._calculate_file_info,
            file_path
        )
        
    def _calculate_file_info(self, file_path: str) -> Dict[str, Any]:
        """计算文件信息。
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict[str, Any]: 文件信息
        """
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
        
        # 计算MD5
        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                md5.update(chunk)
                
        return {
            'path': file_path,
            'size': file_size,
            'md5': md5.hexdigest()
        }
        
    def _is_duplicate_file(self, file_md5: str) -> bool:
        """检查文件是否重复。
        
        Args:
            file_md5: 文件MD5
            
        Returns:
            bool: 是否重复
        """
        try:
            with Session(self.scanner.engine) as session:
                return session.query(Video).filter_by(
                    file_md5=file_md5
                ).first() is not None
        except SQLAlchemyError as e:
            logger.error(f"Failed to check duplicate file: {e}")
            return False
            
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