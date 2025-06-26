"""Twitter/X 下载器模块。

该模块负责从 Twitter/X 平台下载媒体内容。
支持图片和视频的下载。
"""

import os
import re
import json
import time
import logging
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List, Union, Set
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import asdict

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError, DownloadCanceled
from .extractor import TwitterExtractor
from .config import TwitterDownloaderConfig

logger = logging.getLogger(__name__)

class TwitterDownloader(BaseDownloader):
    """Twitter/X 下载器。
    
    支持从推文中下载图片和视频。
    支持代理和超时设置。
    支持自定义文件名模板。
    支持并发和速度限制。
    
    Attributes:
        config: TwitterDownloaderConfig, 下载器配置
        progress_callback: Optional[Callable], 进度回调函数
        semaphore: asyncio.Semaphore, 并发限制信号量
        speed_limiter: Optional[SpeedLimiter], 速度限制器
    """
    
    # GraphQL API 端点和查询
    GRAPHQL_API = "https://api.twitter.com/graphql"
    USER_MEDIA_QUERY_ID = "8dP_-Sh8jQ0VjHwdpW7TuQ"  # 用户媒体查询ID
    
    # GraphQL 查询
    USER_MEDIA_QUERY = """
    query UserMedia($userId: ID!, $count: Int!, $cursor: String) {
      user(id: $userId) {
        media(first: $count, after: $cursor) {
          edges {
            node {
              ... on Tweet {
                id
                createdAt
                text
                author {
                  username
                }
                mediaItems {
                  type
                  url
                  width
                  height
                  duration
                  quality
                }
                stats {
                  likes
                  retweets
                }
              }
            }
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
    """
    
    def __init__(
        self,
        config: TwitterDownloaderConfig,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ):
        """初始化下载器。
        
        Args:
            config: 下载器配置
            progress_callback: 进度回调函数
        """
        super().__init__(save_dir=str(config.save_dir), progress_callback=progress_callback)
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent_downloads)
        self.speed_limiter = SpeedLimiter(config.speed_limit) if config.speed_limit else None
        self.extractor = TwitterExtractor(proxy=config.proxy, timeout=config.timeout)
        self._canceled = False
        
    async def _download_media(self, url: str, save_path: Path, media_type: str) -> bool:
        """下载单个媒体文件。
        
        Args:
            url: 媒体URL
            save_path: 保存路径
            media_type: 媒体类型(photo/video)
            
        Returns:
            bool: 是否下载成功
        """
        async with self.semaphore:  # 使用信号量限制并发
            try:
                total_size = 0
                downloaded_size = 0
                
                async with aiohttp.ClientSession() as session:
                    for retry in range(self.config.max_retries):
                        try:
                            async with session.get(
                                url,
                                headers=self.config.custom_headers,
                                proxy=self.config.proxy,
                                timeout=self.config.timeout
                            ) as response:
                                if response.status != 200:
                                    raise DownloadError(f"HTTP {response.status}: {response.reason}")
                                    
                                total_size = int(response.headers.get("content-length", 0))
                                
                                with open(save_path, "wb") as f:
                                    async for chunk in response.content.iter_chunked(self.config.chunk_size):
                                        if self.is_canceled:
                                            raise DownloadCanceled()
                                            
                                        # 速度限制
                                        if self.speed_limiter:
                                            await self.speed_limiter.wait(len(chunk))
                                            
                                        f.write(chunk)
                                        downloaded_size += len(chunk)
                                        
                                        if total_size:
                                            progress = downloaded_size / total_size
                                            speed = self.speed_limiter.current_speed if self.speed_limiter else 0
                                            status = (
                                                f"下载{media_type}: {downloaded_size}/{total_size} bytes"
                                                f" ({speed/1024:.1f} KB/s)"
                                            )
                                            self.update_progress(progress, status)
                                            
                                return True
                                
                        except asyncio.TimeoutError:
                            logger.warning(f"下载超时，重试 {retry + 1}/{self.config.max_retries}")
                            if retry == self.config.max_retries - 1:
                                raise
                            await asyncio.sleep(2 ** retry)  # 指数退避
                            
                return False
                
            except Exception as e:
                logger.error(f"下载媒体失败: {e}")
                if save_path.exists():
                    save_path.unlink()  # 删除不完整的文件
                return False
                
    def _get_save_path(self, info: Dict[str, Any], media_url: str,
                      media_type: str, index: int) -> Path:
        """生成保存路径。
        
        Args:
            info: 推文信息
            media_url: 媒体URL
            media_type: 媒体类型
            index: 媒体索引
            
        Returns:
            Path: 保存路径
        """
        # 获取文件扩展名
        ext = os.path.splitext(urlparse(media_url).path)[1]
        if not ext:
            ext = ".jpg" if media_type == "photo" else ".mp4"
            
        # 准备模板变量
        created_at = datetime.fromisoformat(info["created_at"].replace("Z", "+00:00"))
        template_vars = {
            "author": info["author"],
            "tweet_id": info["id"],
            "media_type": media_type,
            "index": index + 1,
            "timestamp": int(created_at.timestamp()),
            "date": created_at.strftime("%Y-%m-%d"),
            "time": created_at.strftime("%H-%M-%S"),
            "likes": info.get("likes", 0),
            "reposts": info.get("reposts", 0),
            "quality": info.get("quality", "original"),
            "ext": ext
        }
        
        # 生成文件名
        filename = self.config.filename_template.format(**template_vars)
        return self.config.save_dir / filename
        
    async def _get_user_id(self, username: str) -> str:
        """获取用户ID。
        
        Args:
            username: 用户名
            
        Returns:
            str: 用户ID
            
        Raises:
            ValueError: 获取失败
        """
        # TODO: 实现用户ID获取逻辑
        # 这里需要调用Twitter API
        raise NotImplementedError("用户ID获取功能尚未实现")
        
    async def download_all_from_user(self, username: str, max_items: Optional[int] = None) -> bool:
        """下载用户的所有媒体内容。
        
        Args:
            username: 用户名
            max_items: 最大下载数量
            
        Returns:
            bool: 是否全部下载成功
        """
        try:
            # 获取用户ID
            user_id = await self._get_user_id(username)
            
            cursor = None
            downloaded = 0
            has_more = True
            
            while has_more and (max_items is None or downloaded < max_items):
                # 准备GraphQL查询变量
                variables = {
                    "userId": user_id,
                    "count": min(20, max_items - downloaded if max_items else 20),
                    "cursor": cursor
                }
                
                # 发送GraphQL请求
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.GRAPHQL_API,
                        headers={
                            **self.config.custom_headers,
                            "Authorization": f"Bearer {self.config.api_token}"
                        },
                        json={
                            "query": self.USER_MEDIA_QUERY,
                            "variables": variables
                        },
                        proxy=self.config.proxy,
                        timeout=self.config.timeout
                    ) as response:
                        if response.status != 200:
                            raise DownloadError(f"GraphQL请求失败: HTTP {response.status}")
                            
                        data = await response.json()
                        
                        # 处理错误
                        if "errors" in data:
                            raise DownloadError(f"GraphQL错误: {data['errors']}")
                            
                        # 解析响应
                        media_data = data["data"]["user"]["media"]
                        page_info = media_data["pageInfo"]
                        
                        # 下载媒体
                        for edge in media_data["edges"]:
                            tweet = edge["node"]
                            
                            # 转换为统一格式
                            info = {
                                "id": tweet["id"],
                                "author": tweet["author"]["username"],
                                "created_at": tweet["createdAt"],
                                "text": tweet["text"],
                                "likes": tweet["stats"]["likes"],
                                "reposts": tweet["stats"]["retweets"]
                            }
                            
                            # 下载媒体
                            for i, media in enumerate(tweet["mediaItems"]):
                                media_type = media["type"].lower()
                                file_path = self._get_save_path(info, media["url"], media_type, i)
                                
                                if not await self._download_media(media["url"], file_path, media_type):
                                    logger.error(f"下载失败: {media['url']}")
                                    
                            downloaded += 1
                            if max_items and downloaded >= max_items:
                                break
                                
                        # 更新分页信息
                        has_more = page_info["hasNextPage"]
                        cursor = page_info["endCursor"]
                        
            return True
            
        except Exception as e:
            logger.error(f"下载用户媒体失败: {e}")
            return False
            
    async def download(self, url: str, save_path: Optional[Path] = None) -> bool:
        """下载推文中的媒体内容。
        
        Args:
            url: 推文URL
            save_path: 可选的保存路径，如果不指定则使用默认目录
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            ValueError: URL无效
            DownloadError: 下载失败
        """
        try:
            # 获取推文信息
            info = self.extractor.extract_info(url)
            
            # 确定保存目录
            if save_path is None:
                save_path = self.config.save_dir
            save_path.mkdir(parents=True, exist_ok=True)
            
            # 下载所有媒体
            success = True
            for i, media_url in enumerate(info["media_urls"]):
                # 判断媒体类型
                media_type = "video" if media_url.endswith((".mp4", ".m3u8")) else "photo"
                
                # 生成保存路径
                file_path = self._get_save_path(info, media_url, media_type, i)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 下载媒体
                if not await self._download_media(media_url, file_path, media_type):
                    success = False
                    
            return success
            
        except Exception as e:
            logger.error(f"下载推文失败: {e}")
            raise DownloadError(f"下载推文失败: {e}")
            
    def cancel(self) -> None:
        """取消下载。"""
        self._canceled = True
        logger.info("已请求取消下载")
        
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息。

        Args:
            url: 视频URL

        Returns:
            Dict[str, Any]: 包含视频信息的字典，包含以下键：
                - title: str, 视频标题
                - author: str, 作者
                - quality: str, 视频质量
                
        Raises:
            ValueError: URL格式无效
            ConnectionError: 网络连接错误
            TimeoutError: 请求超时
        """
        try:
            # 获取推文信息
            info = self.extractor.extract_info(url)
            
            # 查找视频URL
            video_url = None
            for media_url in info["media_urls"]:
                if media_url.endswith((".mp4", ".m3u8")):
                    video_url = media_url
                    break
                    
            if not video_url:
                raise ValueError("未找到视频内容")
                
            return {
                "title": info.get("text", "Untitled"),
                "author": info["author"],
                "quality": info.get("quality", "original")
            }
            
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            raise ValueError(f"获取视频信息失败: {e}")
        
class SpeedLimiter:
    """下载速度限制器。
    
    使用令牌桶算法限制下载速度。
    
    Attributes:
        speed_limit: int, 速度限制(bytes/s)
        token_bucket: float, 令牌桶
        last_update: float, 上次更新时间
        window_size: float, 统计窗口大小(秒)
        bytes_transferred: List[tuple], 传输字节统计
    """
    
    def __init__(self, speed_limit: int, window_size: float = 1.0):
        """初始化速度限制器。
        
        Args:
            speed_limit: 速度限制(bytes/s)
            window_size: 统计窗口大小(秒)
        """
        self.speed_limit = speed_limit
        self.token_bucket = speed_limit
        self.last_update = time.monotonic()
        self.window_size = window_size
        self.bytes_transferred = []
        
    async def wait(self, size: int):
        """等待令牌。
        
        Args:
            size: 需要的令牌数(字节数)
        """
        while True:
            now = time.monotonic()
            time_passed = now - self.last_update
            
            # 更新令牌桶
            self.token_bucket = min(
                self.speed_limit,
                self.token_bucket + time_passed * self.speed_limit
            )
            
            if size <= self.token_bucket:
                self.token_bucket -= size
                self.last_update = now
                
                # 记录传输字节数
                self.bytes_transferred.append((now, size))
                # 清理过期记录
                while (self.bytes_transferred and
                       self.bytes_transferred[0][0] < now - self.window_size):
                    self.bytes_transferred.pop(0)
                    
                break
                
            # 计算需要等待的时间
            wait_time = (size - self.token_bucket) / self.speed_limit
            await asyncio.sleep(wait_time)
            
    @property
    def current_speed(self) -> float:
        """当前速度(bytes/s)。"""
        now = time.monotonic()
        # 清理过期记录
        while (self.bytes_transferred and
               self.bytes_transferred[0][0] < now - self.window_size):
            self.bytes_transferred.pop(0)
            
        if not self.bytes_transferred:
            return 0.0
            
        total_bytes = sum(size for _, size in self.bytes_transferred)
        window = min(self.window_size,
                    now - self.bytes_transferred[0][0]) or self.window_size
        return total_bytes / window 