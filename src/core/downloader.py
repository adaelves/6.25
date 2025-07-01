#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
下载器基类模块。

定义下载器的基本接口和通用功能。
支持线程安全的日志记录和文件操作。
"""

import os
import time
import json
import logging
import threading
import hashlib
import asyncio
from typing import Optional, Dict, Any, Callable, Union, List, Set
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum, auto

import requests
import aiohttp
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import yt_dlp
from urllib.parse import urlparse

from .exceptions import DownloadCanceled, DownloadError
from src.utils.cookie_manager import CookieManager

# 配置日志
logger = logging.getLogger(__name__)

# 全局锁
log_lock = threading.Lock()
file_lock = threading.Lock()

class DownloadStatus(Enum):
    """下载状态枚举。"""
    PENDING = auto()
    DOWNLOADING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELED = auto()

@dataclass
class DownloadTask:
    """下载任务数据类。
    
    Attributes:
        url: str, 下载地址
        save_path: Optional[Path], 保存路径
        status: DownloadStatus, 下载状态
        progress: float, 下载进度(0-1)
        error: Optional[Exception], 错误信息
        start_time: float, 开始时间
        end_time: float, 结束时间
        downloaded_size: int, 已下载大小
        total_size: int, 总大小
        speed: float, 下载速度
        retry_count: int, 重试次数
    """
    url: str
    save_path: Optional[Path]
    status: DownloadStatus = DownloadStatus.PENDING
    progress: float = 0.0
    error: Optional[Exception] = None
    start_time: float = 0.0
    end_time: float = 0.0
    downloaded_size: int = 0
    total_size: int = 0
    speed: float = 0.0
    retry_count: int = 0

class DownloadScheduler:
    """下载调度器。
    
    控制并发下载数量，管理下载队列。
    
    Attributes:
        max_concurrency: int, 最大并发数
        max_retries: int, 最大重试次数
        retry_delay: float, 重试延迟(秒)
        tasks: Dict[str, DownloadTask], 任务字典
        active_tasks: Set[str], 活动任务集合
        semaphore: asyncio.Semaphore, 并发控制信号量
        session: aiohttp.ClientSession, 异步HTTP会话
        event_loop: asyncio.AbstractEventLoop, 事件循环
        thread_pool: ThreadPoolExecutor, 线程池
    """
    
    def __init__(
        self,
        max_concurrency: int = 3,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """初始化下载调度器。
        
        Args:
            max_concurrency: 最大并发数，默认3
            max_retries: 最大重试次数，默认3
            retry_delay: 重试延迟(秒)，默认1秒
        """
        self.max_concurrency = max_concurrency
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.tasks: Dict[str, DownloadTask] = {}
        self.active_tasks: Set[str] = set()
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.session: Optional[aiohttp.ClientSession] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread_pool = ThreadPoolExecutor(max_workers=max_concurrency)
        self._shutdown = False
        
        # 创建事件循环
        try:
            self.event_loop = asyncio.get_event_loop()
        except RuntimeError:
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            
    async def _init_session(self):
        """初始化异步HTTP会话。"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=300)  # 5分钟超时
            self.session = aiohttp.ClientSession(timeout=timeout)
            
    async def _close_session(self):
        """关闭异步HTTP会话。"""
        if self.session:
            await self.session.close()
            self.session = None
            
    def _get_task_id(self, url: str, save_path: Optional[Path] = None) -> str:
        """生成任务ID。
        
        Args:
            url: 下载地址
            save_path: 保存路径
            
        Returns:
            str: 任务ID
        """
        components = [url]
        if save_path:
            components.append(str(save_path))
        return hashlib.md5("".join(components).encode()).hexdigest()
        
    async def add_task(
        self,
        downloader: 'BaseDownloader',
        url: str,
        save_path: Optional[Path] = None
    ) -> str:
        """添加下载任务。
        
        Args:
            downloader: 下载器实例
            url: 下载地址
            save_path: 保存路径
            
        Returns:
            str: 任务ID
            
        Raises:
            ValueError: 任务已存在
        """
        task_id = self._get_task_id(url, save_path)
        if task_id in self.tasks:
            raise ValueError(f"任务已存在: {url}")
            
        task = DownloadTask(url=url, save_path=save_path)
        self.tasks[task_id] = task
        
        # 启动下载任务
        asyncio.create_task(self._download_task(task_id, downloader))
        
        return task_id
        
    async def _download_task(self, task_id: str, downloader: 'BaseDownloader'):
        """执行下载任务。
        
        Args:
            task_id: 任务ID
            downloader: 下载器实例
        """
        task = self.tasks[task_id]
        
        # 初始化会话
        await self._init_session()
        
        while task.retry_count <= self.max_retries and not self._shutdown:
            try:
                async with self.semaphore:
                    # 更新任务状态
                    task.status = DownloadStatus.DOWNLOADING
                    task.start_time = time.time()
                    self.active_tasks.add(task_id)
                    
                    # 执行下载
                    await self._do_download(task, downloader)
                    
                    # 下载成功
                    task.status = DownloadStatus.COMPLETED
                    task.end_time = time.time()
                    self.active_tasks.remove(task_id)
                    break
                    
            except Exception as e:
                # 更新错误信息
                task.error = e
                task.retry_count += 1
                
                if task.retry_count <= self.max_retries and not self._shutdown:
                    # 等待重试
                    await asyncio.sleep(self.retry_delay * task.retry_count)
                else:
                    # 达到最大重试次数
                    task.status = DownloadStatus.FAILED
                    if task_id in self.active_tasks:
                        self.active_tasks.remove(task_id)
                    break
                    
    async def _do_download(self, task: DownloadTask, downloader: 'BaseDownloader'):
        """执行实际的下载操作。
        
        Args:
            task: 下载任务
            downloader: 下载器实例
            
        Raises:
            Exception: 下载失败
        """
        # 创建进度回调
        async def progress_callback(progress: float, status: str):
            task.progress = progress
            if 'speed' in status:
                try:
                    speed_str = status.split('speed: ')[1].split('/s')[0]
                    task.speed = self._parse_speed(speed_str)
                except:
                    pass
                    
        # 设置下载器回调
        downloader.progress_callback = progress_callback
        
        # 在线程池中执行同步下载
        await self.event_loop.run_in_executor(
            self.thread_pool,
            downloader.download,
            task.url,
            task.save_path
        )
        
    def _parse_speed(self, speed_str: str) -> float:
        """解析速度字符串。
        
        Args:
            speed_str: 速度字符串(如 "1.2MB")
            
        Returns:
            float: 速度值(字节/秒)
        """
        try:
            value = float(speed_str[:-2])
            unit = speed_str[-2:]
            multiplier = {
                'B': 1,
                'KB': 1024,
                'MB': 1024 * 1024,
                'GB': 1024 * 1024 * 1024
            }.get(unit, 1)
            return value * multiplier
        except:
            return 0.0
            
    def get_task_status(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务状态。
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[DownloadTask]: 任务信息
        """
        return self.tasks.get(task_id)
        
    def cancel_task(self, task_id: str):
        """取消下载任务。
        
        Args:
            task_id: 任务ID
        """
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = DownloadStatus.CANCELED
            if task_id in self.active_tasks:
                self.active_tasks.remove(task_id)
                
    async def cancel_all_tasks(self):
        """取消所有任务。"""
        for task_id in list(self.tasks.keys()):
            self.cancel_task(task_id)
            
    async def shutdown(self):
        """关闭调度器。"""
        self._shutdown = True
        await self.cancel_all_tasks()
        await self._close_session()
        self.thread_pool.shutdown(wait=True)
        
    def __del__(self):
        """析构函数。"""
        if self.event_loop and self.event_loop.is_running():
            asyncio.create_task(self.shutdown())

class BaseDownloader:
    """下载器基类。
    
    提供基本的下载功能和进度回调机制。
    支持线程安全的日志记录和文件操作。
    集成Cookie管理功能。
    默认使用yt-dlp作为下载器。
    
    Attributes:
        platform: str, 平台标识
        save_dir: Path, 保存目录
        progress_callback: Optional[Callable[[float, str], None]], 进度回调函数
        session: requests.Session, 会话对象
        proxy: Optional[str], 代理地址
        timeout: int, 超时时间(秒)
        max_retries: int, 最大重试次数
        cookie_manager: CookieManager, Cookie管理器
        yt_dlp_opts: Dict[str, Any], yt-dlp配置选项
        config: Any, 下载器配置
        speed_limit: Optional[float], 下载速度限制(字节/秒)
        chunk_size: int, 下载块大小(字节)
        buffer_size: int, 写入缓冲区大小(字节)
        scheduler: Optional[DownloadScheduler], 下载调度器
    """
    
    # 错误类型定义
    ERROR_TYPES = {
        'network': {
            'name': '网络错误',
            'suggestions': [
                '检查网络连接是否正常',
                '检查代理设置是否正确',
                '尝试使用代理服务器',
                '等待一段时间后重试'
            ]
        },
        'auth': {
            'name': '认证错误',
            'suggestions': [
                '检查登录状态是否正常',
                '尝试重新登录',
                '检查Cookie是否过期',
                '确认账号权限是否足够'
            ]
        },
        'file': {
            'name': '文件错误',
            'suggestions': [
                '检查磁盘空间是否足够',
                '确认文件名是否合法',
                '检查文件是否被占用',
                '尝试使用其他保存位置'
            ]
        },
        'timeout': {
            'name': '超时错误',
            'suggestions': [
                '检查网络状态',
                '增加超时时间',
                '使用更稳定的网络',
                '尝试分段下载'
            ]
        },
        'format': {
            'name': '格式错误',
            'suggestions': [
                '检查URL是否正确',
                '确认资源是否可用',
                '尝试其他格式',
                '更新下载器版本'
            ]
        }
    }

    # 默认配置
    DEFAULT_CHUNK_SIZE = 8192  # 8KB
    DEFAULT_BUFFER_SIZE = 1024 * 1024  # 1MB
    LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB

    def __init__(
        self,
        platform: str,
        save_dir: Union[str, Path],
        progress_callback: Optional[Callable[[float, str], None]] = None,
        proxy: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3,
        cookie_manager: Optional[CookieManager] = None,
        config: Optional[Any] = None,
        speed_limit: Optional[float] = None,
        chunk_size: Optional[int] = None,
        buffer_size: Optional[int] = None,
        max_concurrency: int = 3
    ):
        """初始化下载器。
        
        Args:
            platform: 平台标识
            save_dir: 保存目录
            progress_callback: 进度回调函数，接收进度(0-1)和状态消息
            proxy: 代理地址(如"http://127.0.0.1:1080")
            timeout: 超时时间(秒)
            max_retries: 最大重试次数
            cookie_manager: Cookie管理器，如果不提供则创建新实例
            config: 下载器配置对象
            speed_limit: 下载速度限制(字节/秒)，None表示不限速
            chunk_size: 下载块大小(字节)，None使用默认值
            buffer_size: 写入缓冲区大小(字节)，None使用默认值
            max_concurrency: 最大并发数，默认3
        """
        self.platform = platform
        self.save_dir = Path(save_dir)
        self.progress_callback = progress_callback
        self.proxy = proxy
        self.timeout = timeout
        self.max_retries = max_retries
        self.is_canceled = False
        self.config = config
        self.speed_limit = speed_limit
        self.chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
        self.buffer_size = buffer_size or self.DEFAULT_BUFFER_SIZE
        self._download_start_time = 0
        self._downloaded_size = 0
        self._download_speeds = []
        self._speed_window_size = 10
        self._last_progress_time = 0
        self._current_file = ""
        self._buffer = bytearray()
        
        # 初始化Cookie管理器
        self.cookie_manager = cookie_manager or CookieManager()
        
        # 创建保存目录
        with file_lock:
            self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建会话
        self.session = self._create_session()
        
        # 记录初始化信息
        with log_lock:
            logger.info(
                f"初始化下载器: platform={platform}, save_dir={save_dir}, "
                f"proxy={proxy}, cookies={bool(self.cookie_manager.get_cookies(platform))}, "
                f"speed_limit={speed_limit if speed_limit else '无限制'}, "
                f"chunk_size={self.chunk_size}, buffer_size={self.buffer_size}"
            )
            
        # 设置yt-dlp配置
        self._setup_yt_dlp()
        
        # 添加调度器
        self.scheduler = DownloadScheduler(
            max_concurrency=max_concurrency,
            max_retries=max_retries
        )
        
    def _create_session(self) -> requests.Session:
        """创建HTTP会话。
        
        Returns:
            requests.Session: 配置好的会话对象
        """
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=10,  # 增加总重试次数
            backoff_factor=2,  # 增加退避因子
            status_forcelist=[408, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527, 530],  # 增加需要重试的状态码
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"],  # 允许所有方法重试
            respect_retry_after_header=True,  # 遵循Retry-After头
            remove_headers_on_redirect=["authorization"]  # 重定向时移除认证头
        )
        
        # 创建适配器
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,  # 增加连接池大小
            pool_maxsize=20,
            pool_block=False
        )
        
        # 配置适配器
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 配置代理
        if self.proxy:
            session.proxies = {
                "http": self.proxy,
                "https": self.proxy
            }
            
        # 配置Cookie
        cookies = self.cookie_manager.get_cookies(self.platform)
        if cookies:
            session.cookies.update(cookies)
            
        # 配置默认请求头
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        })
        
        # 禁用SSL验证
        session.verify = False
        
        return session
        
    def get_download_options(self) -> Dict[str, Any]:
        """获取下载选项。
        
        Returns:
            Dict[str, Any]: 下载选项字典
        """
        options = {
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'proxy': self.proxy,
            'cookies': self.cookie_manager.get_cookies(self.platform),
            'headers': {
                'Cookie': self.cookie_manager.to_header(self.platform)
            }
        }
        
        # 添加Cookie文件路径（如果存在）
        cookie_file = self.cookie_manager.cookie_dir / f"{self.platform}.json"
        if cookie_file.exists():
            options['cookiefile'] = str(cookie_file)
            
        return options
        
    def _generate_filename(self, original_name: str, extension: str = "") -> str:
        """生成唯一的文件名。
        
        Args:
            original_name: 原始文件名
            extension: 文件扩展名(可选)
            
        Returns:
            str: 唯一的文件名
        """
        timestamp = int(time.time())
        if not extension and "." in original_name:
            name, extension = original_name.rsplit(".", 1)
            extension = f".{extension}"
        elif extension and not extension.startswith("."):
            extension = f".{extension}"
            
        # 移除非法字符
        name = "".join(c for c in original_name if c.isalnum() or c in "._- ")
        name = name.strip()
        
        # 生成唯一文件名
        unique_name = f"{name}_{timestamp}{extension}"
        
        # 确保文件名不重复
        with file_lock:
            counter = 1
            while (self.save_dir / unique_name).exists():
                unique_name = f"{name}_{timestamp}_{counter}{extension}"
                counter += 1
                
        return unique_name
        
    def cancel(self):
        """取消下载。"""
        self.is_canceled = True
        with log_lock:
            logger.info("下载已取消")
        
    def check_canceled(self):
        """检查是否已取消。
        
        Raises:
            DownloadCanceled: 如果下载已被取消
        """
        if self.is_canceled:
            with log_lock:
                logger.info("检测到下载取消")
            raise DownloadCanceled("下载已取消")
            
    def update_progress(self, progress: float, status: str) -> None:
        """更新下载进度。
        
        Args:
            progress: 进度值（0-1）
            status: 状态消息
        """
        if self.progress_callback:
            self.progress_callback(progress, status)
            
        with log_lock:
            logger.debug(f"下载进度: {progress*100:.1f}% - {status}")
            
    def _setup_yt_dlp(self):
        """设置yt-dlp下载器配置。"""
        self.yt_dlp_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': str(self.save_dir / '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'progress_hooks': [self._yt_dlp_progress_hook],
            'retries': 10,  # 增加重试次数
            'fragment_retries': 10,  # 增加片段重试次数
            'retry_sleep_functions': {
                'http': lambda n: 5 * (2 ** (n - 1)),  # 指数退避
                'fragment': lambda n: 5 * (2 ** (n - 1)),
                'file_access': lambda n: 5 * (2 ** (n - 1))
            },
            'socket_timeout': self.timeout,
            'http_chunk_size': 1024 * 1024,  # 1MB
            'buffersize': 1024 * 1024 * 10,  # 10MB
            'external_downloader_args': ['--timeout', '30'],
            
            # 代理设置
            'proxy': self.proxy,
            'source_address': '0.0.0.0',  # 使用所有可用网络接口
            
            # SSL设置
            'nocheckcertificate': True,  # 禁用证书验证
            'legacy_server_connect': True,  # 使用旧版服务器连接
            
            # 下载设置
            'concurrent_fragment_downloads': 5,  # 增加并发下载数
            'file_access_retries': 10,  # 增加文件访问重试次数
            'hls_prefer_native': True,  # 使用原生HLS下载器
            'hls_split_discontinuity': True,  # 分割不连续点
            
            # 错误处理
            'ignoreerrors': True,  # 忽略错误继续下载
            'no_abort_on_error': True,  # 错误时不中止
            'no_color': True,  # 禁用颜色输出
            
            # 限速设置
            'ratelimit': 10000000,  # 限速10MB/s
            'throttledratelimit': 5000000,  # 限速5MB/s
            
            # 其他设置
            'prefer_ffmpeg': True,  # 优先使用ffmpeg
            'keepvideo': True,  # 保留源视频
            'writethumbnail': True,  # 下载缩略图
            'writesubtitles': True,  # 下载字幕
            'writeautomaticsub': True,  # 下载自动生成的字幕
            'subtitleslangs': ['zh-CN', 'en'],  # 字幕语言
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }]
        }
        
        # 添加Cookie
        cookies = self.cookie_manager.get_cookies(self.platform)
        if cookies:
            self.yt_dlp_opts['cookiefile'] = str(
                self.cookie_manager.cookie_dir / f"{self.platform}.txt"
            )
            
    def _format_size(self, size: int) -> str:
        """格式化文件大小。
        
        Args:
            size: 文件大小(字节)
            
        Returns:
            str: 格式化后的大小字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
        
    def _format_time(self, seconds: int) -> str:
        """格式化时间。
        
        Args:
            seconds: 秒数
            
        Returns:
            str: 格式化后的时间字符串
        """
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes}分{seconds}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            return f"{hours}时{minutes}分{seconds}秒"
            
    def _calculate_speed(self, chunk_size: int) -> float:
        """计算当前下载速度。
        
        Args:
            chunk_size: 当前块大小(字节)
            
        Returns:
            float: 当前下载速度(字节/秒)
        """
        current_time = time.time()
        if self._last_progress_time > 0:
            time_diff = current_time - self._last_progress_time
            if time_diff > 0:
                speed = chunk_size / time_diff
                self._download_speeds.append(speed)
                # 保持窗口大小
                if len(self._download_speeds) > self._speed_window_size:
                    self._download_speeds.pop(0)
                    
        self._last_progress_time = current_time
        return sum(self._download_speeds) / len(self._download_speeds) if self._download_speeds else 0
        
    def _format_progress_status(
        self,
        downloaded: int,
        total_size: int,
        speed: float,
        filename: str
    ) -> str:
        """格式化进度状态信息。
        
        Args:
            downloaded: 已下载大小(字节)
            total_size: 总大小(字节)
            speed: 下载速度(字节/秒)
            filename: 文件名
            
        Returns:
            str: 格式化后的状态信息
        """
        status_parts = []
        
        # 添加文件名
        if filename:
            status_parts.append(f"文件: {os.path.basename(filename)}")
            
        # 添加下载进度
        if total_size > 0:
            progress_str = f"{self._format_size(downloaded)}/{self._format_size(total_size)}"
            status_parts.append(f"进度: {progress_str}")
            
        # 添加下载速度
        speed_str = f"速度: {self._format_size(int(speed))}/s"
        status_parts.append(speed_str)
        
        # 添加剩余时间
        if speed > 0 and total_size > 0:
            remaining_bytes = total_size - downloaded
            eta = int(remaining_bytes / speed)
            status_parts.append(f"剩余时间: {self._format_time(eta)}")
            
        # 添加速度限制信息
        if self.speed_limit:
            status_parts.append(f"限速: {self._format_size(int(self.speed_limit))}/s")
            
        return " | ".join(status_parts)

    def _handle_network_error(self, e: Exception) -> DownloadError:
        """处理网络错误。
        
        Args:
            e: 原始异常
            
        Returns:
            DownloadError: 处理后的错误
        """
        if isinstance(e, requests.ConnectionError):
            # 连接错误
            error_msg = str(e)
            if "Connection aborted" in error_msg:
                return DownloadError(
                    "连接被中断，可能是网络不稳定或防火墙拦截",
                    "network",
                    "请检查网络连接或尝试使用代理",
                    {
                        "原始错误": error_msg,
                        "代理设置": self.proxy or "未使用代理",
                        "重试次数": self.max_retries,
                        "建议操作": [
                            "检查网络连接是否稳定",
                            "尝试使用代理服务器",
                            "检查防火墙设置",
                            "增加重试次数和超时时间"
                        ]
                    }
                )
            elif "Connection reset" in error_msg:
                return DownloadError(
                    "连接被重置，可能是服务器拒绝访问",
                    "network",
                    "请尝试使用代理或等待一段时间后重试",
                    {
                        "原始错误": error_msg,
                        "代理设置": self.proxy or "未使用代理",
                        "建议操作": [
                            "使用代理服务器",
                            "更换IP地址",
                            "等待一段时间后重试",
                            "检查是否触发反爬虫机制"
                        ]
                    }
                )
            else:
                return DownloadError(
                    "网络连接错误",
                    "network",
                    "请检查网络连接或代理设置",
                    {
                        "原始错误": error_msg,
                        "代理设置": self.proxy or "未使用代理",
                        "重试次数": self.max_retries
                    }
                )
        elif isinstance(e, requests.Timeout):
            # 超时错误
            return DownloadError(
                "请求超时",
                "timeout",
                "请检查网络状态或增加超时时间",
                {
                    "超时时间": f"{self.timeout}秒",
                    "代理设置": self.proxy or "未使用代理",
                    "建议操作": [
                        "检查网络速度",
                        "增加超时时间",
                        "使用更稳定的网络",
                        "尝试使用代理"
                    ]
                }
            )
        elif isinstance(e, requests.HTTPError):
            # HTTP错误
            status_code = e.response.status_code if hasattr(e, 'response') else "未知"
            if status_code in [401, 403]:
                return DownloadError(
                    "无访问权限",
                    "auth",
                    "请检查登录状态或重新登录",
                    {
                        "状态码": status_code,
                        "Cookie状态": bool(self.cookie_manager.get_cookies(self.platform)),
                        "建议操作": [
                            "更新Cookie",
                            "重新登录",
                            "检查账号权限",
                            "等待一段时间后重试"
                        ]
                    }
                )
            elif status_code == 404:
                return DownloadError(
                    "资源不存在",
                    "format",
                    "请检查URL是否正确",
                    {"状态码": status_code}
                )
            elif status_code == 429:
                return DownloadError(
                    "请求过于频繁",
                    "rate_limit",
                    "请降低请求频率或等待一段时间",
                    {
                        "状态码": status_code,
                        "建议操作": [
                            "使用代理轮换",
                            "增加请求间隔",
                            "等待一段时间后重试",
                            "减少并发下载数"
                        ]
                    }
                )
            else:
                return DownloadError(
                    f"HTTP错误: {status_code}",
                    "network",
                    "请稍后重试",
                    {"状态码": status_code}
                )
        else:
            # 其他错误
            return DownloadError(
                f"网络错误: {str(e)}",
                "network",
                "请检查网络连接",
                {
                    "原始错误": str(e),
                    "错误类型": e.__class__.__name__,
                    "建议操作": [
                        "检查网络连接",
                        "检查代理设置",
                        "等待后重试",
                        "查看详细错误日志"
                    ]
                }
            )

    def _handle_file_error(self, e: Exception, path: Optional[Path] = None) -> DownloadError:
        """处理文件错误。
        
        Args:
            e: 原始异常
            path: 文件路径
            
        Returns:
            DownloadError: 处理后的错误
        """
        if isinstance(e, OSError):
            if e.errno == 28:  # No space left on device
                return DownloadError(
                    "磁盘空间不足",
                    "file",
                    "请清理磁盘空间",
                    {
                        "保存路径": str(path or self.save_dir),
                        "错误代码": e.errno
                    }
                )
            elif e.errno == 13:  # Permission denied
                return DownloadError(
                    "无文件访问权限",
                    "file",
                    "请检查文件权限或使用其他保存位置",
                    {
                        "保存路径": str(path or self.save_dir),
                        "错误代码": e.errno
                    }
                )
            else:
                return DownloadError(
                    f"文件操作错误: {str(e)}",
                    "file",
                    "请检查文件系统状态",
                    {
                        "保存路径": str(path or self.save_dir),
                        "错误代码": e.errno if hasattr(e, 'errno') else "未知"
                    }
                )
        else:
            return DownloadError(
                f"文件错误: {str(e)}",
                "file",
                "请检查文件系统",
                {"原始错误": str(e)}
            )

    def _download_stream(
        self,
        response: requests.Response,
        file_obj: Any,
        total_size: int
    ) -> None:
        """流式下载数据。
        
        Args:
            response: 响应对象
            file_obj: 文件对象
            total_size: 总大小
            
        Raises:
            DownloadError: 下载失败
            DownloadCanceled: 下载被取消
        """
        downloaded = 0
        self._buffer = bytearray()
        
        try:
            for chunk in response.iter_content(chunk_size=self.chunk_size):
                # 检查是否取消
                self.check_canceled()
                
                if chunk:
                    # 添加到缓冲区
                    self._buffer.extend(chunk)
                    downloaded += len(chunk)
                    
                    # 如果缓冲区达到阈值，写入文件
                    if len(self._buffer) >= self.buffer_size:
                        file_obj.write(self._buffer)
                        self._buffer.clear()
                    
                    # 应用速度限制
                    self._apply_speed_limit(len(chunk))
                    
                    # 计算下载速度和更新进度
                    speed = self._calculate_speed(len(chunk))
                    if total_size:
                        progress = downloaded / total_size
                        status = self._format_progress_status(
                            downloaded,
                            total_size,
                            speed,
                            str(self._current_file)
                        )
                        self.update_progress(progress, status)
            
            # 写入剩余的缓冲区数据
            if self._buffer:
                file_obj.write(self._buffer)
                self._buffer.clear()
                
        except Exception as e:
            # 清空缓冲区
            self._buffer.clear()
            raise e

    def download(
        self,
        url: str,
        save_path: Optional[Path] = None,
        **kwargs
    ) -> bool:
        """下载文件。
        
        Args:
            url: 下载地址
            save_path: 保存路径，如果不提供则自动生成
            **kwargs: 其他参数
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            DownloadError: 下载失败
            DownloadCanceled: 下载被取消
        """
        try:
            # 重置下载统计
            self._download_start_time = time.time()
            self._downloaded_size = 0
            self._download_speeds = []
            self._last_progress_time = 0
            
            # 验证URL
            if not self._validate_url(url):
                raise DownloadError(
                    "无效的URL",
                    "format",
                    "请检查URL格式是否正确",
                    {"URL": url}
                )
                
            # 获取保存路径
            if not save_path:
                parsed_url = urlparse(url)
                filename = os.path.basename(parsed_url.path)
                if not filename:
                    filename = f"download_{int(time.time())}"
                save_path = self.save_dir / self._generate_filename(filename)
                
            try:
                # 确保目录存在
                save_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise self._handle_file_error(e, save_path)
            
            # 开始下载
            with log_lock:
                logger.info(f"开始下载: {url} -> {save_path}")
                
            try:
                response = self.session.get(
                    url,
                    stream=True,
                    timeout=self.timeout,
                    **kwargs
                )
                response.raise_for_status()
            except Exception as e:
                raise self._handle_network_error(e)
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            self._current_file = str(save_path)
            
            # 根据文件大小调整缓冲区
            if total_size > self.LARGE_FILE_THRESHOLD:
                self.chunk_size = min(self.chunk_size * 2, 1024 * 1024)  # 最大1MB
                self.buffer_size = min(self.buffer_size * 2, 10 * 1024 * 1024)  # 最大10MB
                
            # 下载文件
            try:
                with open(save_path, 'wb', buffering=self.buffer_size) as f:
                    self._download_stream(response, f, total_size)
            except Exception as e:
                raise self._handle_file_error(e, save_path)
                
            return True
            
        except DownloadError:
            raise
        except Exception as e:
            with log_lock:
                logger.error(f"下载失败: {url} -> {str(e)}")
            raise DownloadError(
                f"下载失败: {str(e)}",
                "未知错误",
                "请检查日志获取详细信息",
                {
                    "URL": url,
                    "保存路径": str(save_path) if save_path else "未指定",
                    "原始错误": str(e)
                }
            )

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息。
        
        使用yt-dlp提取视频信息。
        
        Args:
            url: 视频URL
            
        Returns:
            Dict[str, Any]: 视频信息字典
            
        Raises:
            ValueError: URL无效
            DownloadError: 信息提取失败
        """
        try:
            with yt_dlp.YoutubeDL(self.yt_dlp_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', ''),
                    'author': info.get('uploader', ''),
                    'quality': info.get('format', ''),
                    'duration': info.get('duration', 0),
                    'view_count': info.get('view_count', 0),
                    'like_count': info.get('like_count', 0),
                    'description': info.get('description', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'formats': info.get('formats', []),
                }
        except Exception as e:
            raise DownloadError(f"获取视频信息失败: {str(e)}")

    def close(self):
        """关闭下载器。"""
        if self.session:
            self.session.close()
            with log_lock:
                logger.info("下载器已关闭")

    def _validate_url(self, url: str) -> bool:
        """验证URL格式是否有效。

        Args:
            url: 要验证的URL

        Returns:
            bool: URL是否有效
        """
        # TODO: 实现URL验证逻辑
        return True 

    def _remove_duplicates(self, media_list: List[Dict[str, Any]], delete_duplicates: bool = True) -> List[Dict[str, Any]]:
        """基于MD5的文件去重。
        
        通过计算文件的MD5哈希值来识别并移除重复的媒体文件。
        
        Args:
            media_list: 媒体文件列表，每个项目包含'path'键
            delete_duplicates: 是否删除重复文件，默认为True
            
        Returns:
            List[Dict[str, Any]]: 去重后的媒体文件列表
        """
        with log_lock:
            logger.info(f"开始文件去重，共 {len(media_list)} 个文件")
            
        unique = {}
        for item in media_list:
            try:
                file_path = item.get('path')
                if not file_path or not os.path.exists(file_path):
                    with log_lock:
                        logger.warning(f"文件不存在或路径无效: {file_path}")
                    continue
                    
                with open(file_path, 'rb') as f:
                    md5 = hashlib.md5(f.read()).hexdigest()
                    
                if md5 not in unique:
                    unique[md5] = item
                elif delete_duplicates:
                    # 如果是重复文件且启用了删除功能，则删除它
                    try:
                        os.remove(file_path)
                        with log_lock:
                            logger.info(f"删除重复文件: {file_path}")
                    except Exception as e:
                        with log_lock:
                            logger.warning(f"删除重复文件失败: {file_path} - {str(e)}")
                            
            except Exception as e:
                with log_lock:
                    logger.error(f"处理文件失败: {item.get('path', 'unknown')} - {str(e)}")
                # 如果无法处理，保留该文件
                unique[item.get('path', str(time.time()))] = item
                
        result = list(unique.values())
        
        with log_lock:
            logger.info(f"文件去重完成: 原始文件数 {len(media_list)}，去重后文件数 {len(result)}")
            if len(media_list) > len(result):
                logger.info(f"共删除 {len(media_list) - len(result)} 个重复文件")
                
        return result

    def remove_duplicates_in_dir(self, directory: Union[str, Path] = None, recursive: bool = True) -> Dict[str, Any]:
        """对指定目录中的所有媒体文件进行去重。
        
        Args:
            directory: 要处理的目录，默认为下载器的保存目录
            recursive: 是否递归处理子目录，默认为True
            
        Returns:
            Dict[str, Any]: 去重结果统计
        """
        directory = Path(directory) if directory else self.save_dir
        
        with log_lock:
            logger.info(f"开始处理目录: {directory}")
            
        # 收集所有媒体文件
        media_files = []
        for ext in ['.mp4', '.ts', '.m4a', '.mp3', '.jpg', '.jpeg', '.png', '.gif']:
            if recursive:
                pattern = f"**/*{ext}"
            else:
                pattern = f"*{ext}"
            media_files.extend([
                {'path': str(p)} for p in directory.glob(pattern)
            ])
            
        # 执行去重
        original_count = len(media_files)
        unique_files = self._remove_duplicates(media_files)
        final_count = len(unique_files)
        
        result = {
            'directory': str(directory),
            'original_count': original_count,
            'final_count': final_count,
            'removed_count': original_count - final_count,
            'recursive': recursive
        }
        
        with log_lock:
            logger.info(
                f"目录去重完成: {result['directory']}\n"
                f"原始文件数: {result['original_count']}\n"
                f"去重后文件数: {result['final_count']}\n"
                f"删除重复文件数: {result['removed_count']}"
            )
            
        return result 

    def _apply_speed_limit(self, chunk_size: int):
        """应用速度限制。
        
        Args:
            chunk_size: 当前块大小(字节)
        """
        if not self.speed_limit:
            return
            
        self._downloaded_size += chunk_size
        elapsed_time = time.time() - self._download_start_time
        
        # 计算期望时间
        expected_time = self._downloaded_size / self.speed_limit
        
        # 如果实际时间小于期望时间，则等待
        if elapsed_time < expected_time:
            time.sleep(expected_time - elapsed_time)

    def _yt_dlp_progress_hook(self, d: Dict[str, Any]):
        """yt-dlp进度回调。
        
        Args:
            d: 进度信息字典
        """
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            filename = d.get('filename', '')
            
            if total > 0:
                progress = downloaded / total
                status = self._format_progress_status(
                    downloaded,
                    total,
                    speed,
                    filename
                )
                self.update_progress(progress, status)
                
        elif d['status'] == 'finished':
            self.update_progress(1.0, "下载完成") 

    async def async_download(
        self,
        url: str,
        save_path: Optional[Path] = None
    ) -> str:
        """异步下载文件。
        
        Args:
            url: 下载地址
            save_path: 保存路径
            
        Returns:
            str: 任务ID
        """
        return await self.scheduler.add_task(self, url, save_path)
        
    def get_download_status(self, task_id: str) -> Optional[DownloadTask]:
        """获取下载状态。
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[DownloadTask]: 任务信息
        """
        return self.scheduler.get_task_status(task_id)
        
    def cancel_download(self, task_id: str):
        """取消下载。
        
        Args:
            task_id: 任务ID
        """
        self.scheduler.cancel_task(task_id)
        
    async def shutdown(self):
        """关闭下载器。"""
        await self.scheduler.shutdown()
        self.close() 