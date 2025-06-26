"""Twitter/X 下载器模块。

该模块负责从 Twitter/X 平台下载媒体内容。
支持图片和视频的下载。
"""

import os
import re
import json
import time
import logging
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import (
    Page,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError
)

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError, DownloadCanceled
from .config import TwitterDownloaderConfig
from .extractor import TwitterExtractor

logger = logging.getLogger(__name__)

class TwitterDownloader(BaseDownloader):
    """Twitter/X 下载器。
    
    支持从推文中下载图片和视频。
    支持代理和超时设置。
    支持自定义文件名模板。
    支持并发和速度限制。
    """
    
    # 视频元素选择器列表
    VIDEO_SELECTORS = [
        "video",  # 标准video标签
        "div[data-testid='videoPlayer'] video",  # Twitter视频播放器
        "div[data-testid='videoComponent'] video",  # Twitter视频组件
        "div[data-testid='media'] video",  # 媒体容器中的视频
        "article video",  # 文章中的视频
    ]
    
    # 图片元素选择器列表
    IMAGE_SELECTORS = [
        "img[src*='media']",  # 媒体图片
        "div[data-testid='media'] img",  # 媒体容器中的图片
        "article img[src*='media']",  # 文章中的媒体图片
    ]
    
    def __init__(
        self,
        config: TwitterDownloaderConfig,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        extractor: Optional[TwitterExtractor] = None
    ):
        """初始化下载器。
        
        Args:
            config: 下载器配置
            progress_callback: 进度回调函数
            extractor: 视频提取器实例，如果不提供则创建新实例
        """
        super().__init__(save_dir=str(config.save_dir), progress_callback=progress_callback)
        self.config = config
        self.extractor = extractor or TwitterExtractor()
        self._canceled = False
        
    def _wait_for_video(self, page: Page) -> None:
        """等待视频元素加载。
        
        Args:
            page: Playwright页面对象
            
        Raises:
            PlaywrightTimeoutError: 等待超时
            PlaywrightError: 元素已分离
        """
        try:
            # 等待视频元素出现
            video = page.wait_for_selector(
                'video',
                state='attached',
                timeout=10000  # 10秒超时
            )
            
            if not video:
                raise PlaywrightError("Element is detached")
                
            # 尝试访问元素属性以确保它仍然存在
            try:
                # 使用 evaluate 检查元素是否仍然在 DOM 中
                is_attached = page.evaluate("""() => {
                    const video = document.querySelector('video');
                    return video && video.isConnected;
                }""")
                
                if not is_attached:
                    raise PlaywrightError("Element is detached")
                    
            except PlaywrightError as e:
                if 'detached' in str(e):
                    logger.warning("视频元素已分离，将重新加载页面")
                    raise PlaywrightError("Element is detached")
                raise
                
        except PlaywrightError as e:
            if 'detached' in str(e):
                logger.warning("视频元素已分离，将重新加载页面")
                raise PlaywrightError("Element is detached")
            raise
            
    def download_video(self, page: Page) -> List[str]:
        """下载视频。
        
        Args:
            page: Playwright页面对象
            
        Returns:
            List[str]: 下载的视频URL列表
            
        Raises:
            PlaywrightError: 页面操作失败
            ValueError: 未找到视频元素
        """
        retry_count = 0
        last_error = None
        
        while retry_count < self.config.max_retries:
            try:
                # 等待视频元素加载
                self._wait_for_video(page)
                
                # 提取视频URL
                urls = self.extractor.extract_media(page)
                if not urls:
                    raise ValueError("未找到视频元素")
                    
                return urls
                
            except PlaywrightError as e:
                retry_count += 1
                last_error = e
                
                if "Element is detached" in str(e):
                    logger.warning(
                        "视频元素已分离(尝试 %d/%d): %s",
                        retry_count,
                        self.config.max_retries,
                        str(e)
                    )
                else:
                    logger.warning(
                        "视频元素加载失败(尝试 %d/%d): %s",
                        retry_count,
                        self.config.max_retries,
                        str(e)
                    )
                
                if retry_count < self.config.max_retries:
                    # 重试前等待
                    time.sleep(self.config.retry_interval)
                    
        # 所有重试都失败
        logger.error("视频下载失败，已达到最大重试次数: %s", str(last_error))
        raise last_error
        
    def cancel(self) -> None:
        """取消下载。"""
        self._canceled = True
        logger.info("已请求取消下载")
        
    def download(self, url: str, save_path: Optional[Path] = None) -> bool:
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
        raise NotImplementedError("同步下载方法尚未实现")
        
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
        raise NotImplementedError("同步获取视频信息方法尚未实现")

class SpeedLimiter:
    """下载速度限制器。
    
    使用令牌桶算法限制下载速度。
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