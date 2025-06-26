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
from collections import deque

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError, DownloadCanceled
from .config import TwitterDownloaderConfig

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
        self._canceled = False
        
        # 浏览器相关属性
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._browser_lock = asyncio.Lock()
        
    async def _init_browser(self) -> None:
        """初始化浏览器实例。"""
        if not self._browser:
            async with self._browser_lock:
                if not self._browser:  # 双重检查锁定
                    logger.info("初始化浏览器...")
                    playwright = await async_playwright().start()
                    self._browser = await playwright.chromium.launch(
                        headless=True,
                        proxy={"server": self.config.proxy} if self.config.proxy else None
                    )
                    self._context = await self._browser.new_context(
                        user_agent=self.config.custom_headers.get("User-Agent"),
                        viewport={"width": 1920, "height": 1080}
                    )
                    logger.info("浏览器初始化完成")
                    
    async def _get_page(self) -> Page:
        """获取新的页面实例。
        
        Returns:
            Page: Playwright页面对象
        """
        await self._init_browser()
        if not self._context:
            raise RuntimeError("浏览器上下文未初始化")
        return await self._context.new_page()
        
    async def close(self) -> None:
        """关闭下载器，释放资源。"""
        if self._browser:
            try:
                if self._context:
                    await self._context.close()
                await self._browser.close()
                logger.info("浏览器已关闭")
            except Exception as e:
                logger.error(f"关闭浏览器时出错: {e}")
            finally:
                self._browser = None
                self._context = None
                
    async def __aenter__(self):
        """异步上下文管理器入口。"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口。"""
        await self.close()
        
    def __del__(self):
        """析构函数。"""
        if self._browser:
            logger.warning("下载器在析构时仍有活动的浏览器实例")
            asyncio.create_task(self.close())
            
    async def _wait_for_network_idle(self, page: Page, timeout: int = 30000):
        """等待网络请求完成。
        
        Args:
            page: Playwright页面对象
            timeout: 超时时间（毫秒）
        """
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout)
            logger.info("网络请求已完成")
        except Exception as e:
            logger.warning(f"等待网络请求完成超时: {e}")
            
    async def _scroll_page(self, page: Page):
        """滚动页面以触发懒加载。
        
        Args:
            page: Playwright页面对象
        """
        try:
            # 滚动到页面底部
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)  # 等待内容加载
            
            # 滚动回顶部
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)
            
            logger.info("页面滚动完成")
        except Exception as e:
            logger.warning(f"页面滚动失败: {e}")
            
    async def _try_find_element(self, page: Page, selectors: List[str], timeout: int = 5000) -> Optional[Any]:
        """尝试使用多个选择器查找元素。
        
        Args:
            page: Playwright页面对象
            selectors: 选择器列表
            timeout: 每个选择器的超时时间（毫秒）
            
        Returns:
            Optional[Any]: 找到的元素，未找到返回None
        """
        for selector in selectors:
            try:
                logger.info(f"尝试使用选择器: {selector}")
                element = await page.wait_for_selector(selector, timeout=timeout)
                if element:
                    logger.info(f"找到元素: {selector}")
                    return element
            except Exception as e:
                logger.debug(f"选择器 {selector} 未找到元素: {e}")
                continue
        return None
        
    async def _extract_video_url(self, url: str) -> Dict[str, Any]:
        """提取视频信息。
        
        Args:
            url: 推文URL
            
        Returns:
            Dict[str, Any]: 视频信息字典
            
        Raises:
            ValueError: 未找到视频
        """
        logger.info(f"提取视频信息: {url}")
        
        # 从URL中提取推文ID
        match = re.match(r"https://twitter\.com/\w+/status/(\d+)", url)
        if not match:
            raise ValueError("无效的Twitter URL")
            
        try:
            # 获取页面实例
            page = await self._get_page()
            
            try:
                # 设置超时
                page.set_default_timeout(60000)  # 增加到60秒
                
                # 启用请求拦截
                await page.route("**/*", lambda route: route.continue_())
                page.on("request", lambda request: logger.debug(f"请求: {request.url}"))
                page.on("response", lambda response: logger.debug(f"响应: {response.url} ({response.status})"))
                
                # 访问推文页面
                logger.info("正在访问页面...")
                await page.goto(url, wait_until="networkidle", timeout=60000)
                logger.info("页面加载完成")
                
                # 等待页面渲染和网络请求完成
                await self._wait_for_network_idle(page)
                
                # 滚动页面以触发懒加载
                await self._scroll_page(page)
                
                # 保存页面截图用于调试
                await page.screenshot(path="debug_screenshot.png")
                logger.info("已保存页面截图")
                
                # 获取页面HTML用于调试
                html_content = await page.content()
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info("已保存页面HTML")
                
                # 尝试查找视频元素
                video_element = await self._try_find_element(page, self.VIDEO_SELECTORS)
                if video_element:
                    logger.info("找到视频元素")
                    video_urls = []
                    
                    # 获取video标签的src属性
                    src = await video_element.get_attribute("src")
                    if src:
                        video_urls.append(src)
                        logger.info(f"找到视频URL(从src): {src}")
                        
                    # 获取source标签的src属性
                    sources = await video_element.query_selector_all("source")
                    for source in sources:
                        src = await source.get_attribute("src")
                        if src:
                            video_urls.append(src)
                            logger.info(f"找到视频URL(从source): {src}")
                            
                    if video_urls:
                        # 获取推文文本
                        tweet_text = ""
                        article = await page.query_selector("article")
                        if article:
                            text_elements = await article.query_selector_all("[lang]")
                            if text_elements:
                                tweet_text = await text_elements[0].text_content()
                                logger.info(f"找到推文文本: {tweet_text[:100]}")
                                
                        # 返回最高质量的视频URL
                        best_url = video_urls[0]  # 默认使用第一个URL
                        max_bitrate = 0
                        
                        for url in video_urls:
                            if "vid/720p" in url:
                                best_url = url
                                max_bitrate = 720
                                logger.info("找到720p视频")
                            elif "vid/1080p" in url and max_bitrate < 1080:
                                best_url = url
                                max_bitrate = 1080
                                logger.info("找到1080p视频")
                                
                        return {
                            "url": best_url,
                            "title": tweet_text[:100] if tweet_text else "",  # 限制标题长度
                            "ext": "mp4",
                            "filesize": 0,  # 无法预先获取文件大小
                            "format_id": str(max_bitrate)
                        }
                        
                # 如果没有找到视频，尝试查找图片
                image_element = await self._try_find_element(page, self.IMAGE_SELECTORS)
                if image_element:
                    logger.info("找到图片元素")
                    src = await image_element.get_attribute("src")
                    if src and "media" in src:
                        # 获取最高质量的图片URL
                        best_url = src
                        if "format=jpg&name=large" in src:
                            best_url = src
                            
                        logger.info(f"选择最佳图片URL: {best_url}")
                        return {
                            "url": best_url,
                            "title": "",  # 图片不需要标题
                            "ext": "jpg",
                            "filesize": 0,
                            "format_id": "large"
                        }
                        
                raise ValueError("未找到视频或图片元素")
                
            finally:
                await page.close()
                
        except Exception as e:
            logger.error(f"提取视频信息失败: {e}")
            raise ValueError(f"提取视频信息失败: {e}")
            
    async def _download_video(self, video_info: Dict[str, Any], save_path: Path) -> bool:
        """下载视频。
        
        Args:
            video_info: 视频信息字典
            save_path: 保存路径
            
        Returns:
            bool: 是否下载成功
        """
        async with self.semaphore:  # 使用信号量限制并发
            try:
                downloaded_size = 0
                start_time = time.monotonic()
                chunk_times: deque = deque(maxlen=50)  # 用于计算实时速度
                
                logger.info(f"开始下载视频: {video_info['url']}")
                
                async with aiohttp.ClientSession() as session:
                    for retry in range(self.config.max_retries):
                        try:
                            async with session.get(
                                video_info['url'],
                                headers=self.config.custom_headers,
                                proxy=self.config.proxy,
                                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                                ssl=False  # 禁用SSL验证以便调试
                            ) as response:
                                if response.status != 200:
                                    error_text = await response.text()
                                    logger.error(
                                        f"HTTP {response.status}: {response.reason}\n"
                                        f"Response headers: {response.headers}\n"
                                        f"Response body: {error_text[:500]}..."
                                    )
                                    raise DownloadError(f"HTTP {response.status}: {response.reason}")
                                    
                                total_size = int(response.headers.get("content-length", 0))
                                logger.info(f"文件大小: {total_size/1024/1024:.2f} MB")
                                
                                with open(save_path, "wb") as f:
                                    async for chunk in response.content.iter_chunked(self.config.chunk_size):
                                        if self._canceled:
                                            logger.info("下载已取消")
                                            raise DownloadCanceled()
                                            
                                        # 速度限制
                                        if self.speed_limiter:
                                            await self.speed_limiter.wait(len(chunk))
                                            
                                        # 写入数据块并立即释放内存
                                        f.write(chunk)
                                        f.flush()  # 确保立即写入磁盘
                                        
                                        # 更新下载进度
                                        chunk_time = time.monotonic()
                                        chunk_times.append((chunk_time, len(chunk)))
                                        downloaded_size += len(chunk)
                                        
                                        # 计算实时速度
                                        if chunk_times:
                                            window_start = chunk_times[0][0]
                                            window_bytes = sum(size for _, size in chunk_times)
                                            window_time = chunk_time - window_start
                                            current_speed = window_bytes / window_time if window_time > 0 else 0
                                        else:
                                            current_speed = 0
                                        
                                        # 更新进度
                                        if total_size:
                                            progress = downloaded_size / total_size
                                            eta = ((total_size - downloaded_size) / current_speed) if current_speed > 0 else 0
                                            status = (
                                                f"下载视频: {downloaded_size}/{total_size} bytes "
                                                f"({current_speed/1024:.1f} KB/s) "
                                                f"ETA: {int(eta)}s"
                                            )
                                            if self.progress_callback:
                                                self.progress_callback(progress, status)
                                                
                                logger.info(f"下载完成: {video_info['url']}")
                                return True
                                
                        except aiohttp.ClientError as e:
                            logger.warning(f"下载出错 ({retry + 1}/{self.config.max_retries}): {e}")
                            if retry == self.config.max_retries - 1:
                                raise
                            await asyncio.sleep(2 ** retry)  # 指数退避
                            
                return False
                
            except DownloadCanceled:
                logger.info(f"取消下载: {video_info['url']}")
                if save_path.exists():
                    save_path.unlink()  # 删除不完整的文件
                return False
                
            except Exception as e:
                logger.error(f"下载媒体失败: {e}")
                if save_path.exists():
                    save_path.unlink()  # 删除不完整的文件
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
            logger.info(f"开始处理推文: {url}")
            
            # 确定保存目录
            if save_path is None:
                save_path = self.config.save_dir
            save_path.mkdir(parents=True, exist_ok=True)
            
            # 提取视频信息
            video_info = await self._extract_video_url(url)
            
            # 生成保存路径
            file_path = save_path / f"{os.path.basename(urlparse(url).path)}.{video_info['ext']}"
            
            # 下载视频
            return await self._download_video(video_info, file_path)
            
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