"""YouTube播放列表下载器模块。

该模块负责从YouTube下载播放列表。
支持并发下载和进度跟踪。
"""

import re
import logging
import asyncio
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
import yt_dlp
from concurrent.futures import ThreadPoolExecutor

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError
from .downloader import YouTubeDownloader

logger = logging.getLogger(__name__)

class YouTubePlaylistDownloader(BaseDownloader):
    """YouTube播放列表下载器。
    
    支持两种播放列表URL格式：
    1. https://youtube.com/playlist?list=PLAYLIST_ID
    2. https://youtu.be/VIDEO_ID?list=PLAYLIST_ID
    
    支持并发下载，可限制并发数防止被封禁。
    
    Attributes:
        save_dir: str, 保存目录
        progress_callback: Optional[Callable], 进度回调函数
        proxy: Optional[str], 代理服务器地址
        timeout: float, 网络请求超时时间（秒）
        max_height: int, 最大视频高度（像素）
        prefer_quality: str, 优先选择的视频质量
        merge_output_format: str, 合并后的输出格式
    """
    
    # 播放列表URL正则表达式
    PLAYLIST_PATTERNS = [
        r'youtube\.com/playlist\?list=([^&]+)',  # 标准播放列表URL
        r'youtu\.be/[^?]+\?list=([^&]+)',  # 视频带播放列表URL
        r'youtube\.com/watch\?.*list=([^&]+)'  # 视频页面带播放列表URL
    ]
    
    def __init__(self,
                 save_dir: str,
                 progress_callback: Optional[Callable[[float, str], None]] = None,
                 proxy: Optional[str] = None,
                 timeout: float = 30.0,
                 max_height: int = 1080,
                 prefer_quality: str = '1080p',
                 merge_output_format: str = 'mp4'):
        """初始化下载器。
        
        Args:
            save_dir: 保存目录
            progress_callback: 进度回调函数
            proxy: 可选的代理服务器地址
            timeout: 网络请求超时时间
            max_height: 最大视频高度
            prefer_quality: 优先选择的视频质量
            merge_output_format: 合并后的输出格式
        """
        super().__init__(save_dir=save_dir, progress_callback=progress_callback)
        
        # 创建单个视频下载器
        self.video_downloader = YouTubeDownloader(
            save_dir=save_dir,
            proxy=proxy,
            timeout=timeout,
            max_height=max_height,
            prefer_quality=prefer_quality,
            merge_output_format=merge_output_format
        )
        
        # 保存配置
        self.proxy = proxy
        self.timeout = timeout
        
        # 下载进度
        self._total_videos = 0
        self._completed_videos = 0
        
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取播放列表信息。
        
        Args:
            url: 播放列表URL
            
        Returns:
            Dict[str, Any]: 包含播放列表信息的字典，包含以下键：
                - title: str, 播放列表标题
                - video_count: int, 视频数量
                - videos: List[Dict], 视频列表，每个视频包含：
                    - id: str, 视频ID
                    - title: str, 视频标题
                    - duration: int, 视频时长（秒）
                
        Raises:
            ValueError: URL格式无效
            DownloadError: 获取失败
        """
        try:
            # 验证URL格式
            playlist_id = None
            for pattern in self.PLAYLIST_PATTERNS:
                match = re.search(pattern, url)
                if match:
                    playlist_id = match.group(1)
                    break
                    
            if not playlist_id:
                raise ValueError(f"无效的播放列表URL: {url}")
                
            # 配置yt-dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,  # 只提取视频信息，不下载
                'nocheckcertificate': True,
            }
            
            if self.proxy:
                ydl_opts['proxy'] = self.proxy
                
            # 获取播放列表信息
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"正在获取播放列表信息: {url}")
                info = ydl.extract_info(url, download=False)
                
                if 'entries' not in info:
                    raise DownloadError("无法获取播放列表内容")
                    
                # 提取视频信息
                videos = []
                for entry in info['entries']:
                    if entry and 'id' in entry:
                        videos.append({
                            'id': entry['id'],
                            'title': entry.get('title', '未知标题'),
                            'duration': entry.get('duration', 0)
                        })
                        
                return {
                    'title': info.get('title', '未知播放列表'),
                    'video_count': len(videos),
                    'videos': videos
                }
                
        except Exception as e:
            logger.error(f"获取播放列表信息失败: {e}")
            raise DownloadError(f"获取播放列表信息失败: {e}")
        
    def get_video_ids(self, url: str) -> List[str]:
        """获取播放列表中的所有视频ID。
        
        Args:
            url: 播放列表URL
            
        Returns:
            List[str]: 视频ID列表
            
        Raises:
            ValueError: URL格式无效
            DownloadError: 获取失败
        """
        # 验证URL格式
        playlist_id = None
        for pattern in self.PLAYLIST_PATTERNS:
            match = re.search(pattern, url)
            if match:
                playlist_id = match.group(1)
                break
                
        if not playlist_id:
            raise ValueError(f"无效的播放列表URL: {url}")
            
        try:
            # 配置yt-dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,  # 只提取视频信息，不下载
                'nocheckcertificate': True,
            }
            
            if self.proxy:
                ydl_opts['proxy'] = self.proxy
                
            # 获取播放列表信息
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"正在获取播放列表信息: {url}")
                info = ydl.extract_info(url, download=False)
                
                if 'entries' not in info:
                    raise DownloadError("无法获取播放列表内容")
                    
                # 提取视频ID
                video_ids = []
                for entry in info['entries']:
                    if entry and 'id' in entry:
                        video_ids.append(entry['id'])
                        
                logger.info(f"找到 {len(video_ids)} 个视频")
                return video_ids
                
        except Exception as e:
            if isinstance(e, ValueError):
                raise e
            logger.error(f"获取播放列表失败: {e}")
            raise DownloadError(f"获取播放列表失败: {e}")
            
    async def _download_video(self, video_id: str) -> bool:
        """下载单个视频。
        
        Args:
            video_id: 视频ID
            
        Returns:
            bool: 是否下载成功
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            # 下载视频
            success = await asyncio.get_event_loop().run_in_executor(
                None, self.video_downloader.download, url
            )
            
            # 更新进度
            if success:
                self._completed_videos += 1
                progress = self._completed_videos / self._total_videos
                self.update_progress(
                    progress,
                    f"已完成: {self._completed_videos}/{self._total_videos}"
                )
                
            return success
            
        except Exception as e:
            logger.error(f"下载视频失败 {video_id}: {e}")
            return False
            
    async def _download_videos(self, video_ids: List[str], concurrency: int):
        """并发下载多个视频。
        
        Args:
            video_ids: 视频ID列表
            concurrency: 并发数
        """
        # 创建任务
        tasks = []
        semaphore = asyncio.Semaphore(concurrency)
        
        async def download_with_semaphore(video_id: str):
            async with semaphore:
                return await self._download_video(video_id)
                
        for video_id in video_ids:
            task = asyncio.create_task(download_with_semaphore(video_id))
            tasks.append(task)
            
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = sum(1 for r in results if r is True)
        logger.info(f"下载完成: 成功 {success_count}/{len(video_ids)}")
            
    def download_all(self, url: str, concurrency: int = 3) -> bool:
        """下载播放列表中的所有视频。
        
        Args:
            url: 播放列表URL
            concurrency: 并发下载数，默认为3
            
        Returns:
            bool: 是否全部下载成功
            
        Raises:
            ValueError: URL格式无效
            DownloadError: 下载失败
        """
        try:
            # 获取视频ID列表
            video_ids = self.get_video_ids(url)
            if not video_ids:
                raise DownloadError("播放列表为空")
                
            # 初始化进度
            self._total_videos = len(video_ids)
            self._completed_videos = 0
            
            # 创建事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 运行下载任务
                loop.run_until_complete(
                    self._download_videos(video_ids, concurrency)
                )
                return True
                
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"下载播放列表失败: {e}")
            raise DownloadError(f"下载播放列表失败: {e}")
            
    def download(self, url: str, **kwargs) -> bool:
        """实现基类的下载方法。
        
        这里直接调用 download_all 方法。
        
        Args:
            url: 播放列表URL
            **kwargs: 其他参数
            
        Returns:
            bool: 是否下载成功
        """
        concurrency = kwargs.get('concurrency', 3)
        return self.download_all(url, concurrency) 