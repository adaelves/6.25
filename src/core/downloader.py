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
from typing import Optional, Dict, Any, Callable, Union, List
from pathlib import Path
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import yt_dlp

from .exceptions import DownloadCanceled
from ..utils.cookie_manager import CookieManager

# 配置日志
logger = logging.getLogger(__name__)

# 全局锁
log_lock = threading.Lock()
file_lock = threading.Lock()

class DownloadError(Exception):
    """下载错误。"""
    pass

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
    """
    
    def __init__(
        self,
        platform: str,
        save_dir: Union[str, Path],
        progress_callback: Optional[Callable[[float, str], None]] = None,
        proxy: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3,
        cookie_manager: Optional[CookieManager] = None,
        config: Optional[Any] = None
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
        """
        self.platform = platform
        self.save_dir = Path(save_dir)
        self.progress_callback = progress_callback
        self.proxy = proxy
        self.timeout = timeout
        self.max_retries = max_retries
        self.is_canceled = False
        self.config = config
        
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
                f"proxy={proxy}, cookies={bool(self.cookie_manager.get_cookies(platform))}"
            )
            
        # 设置yt-dlp配置
        self._setup_yt_dlp()
        
    def _create_session(self) -> requests.Session:
        """创建HTTP会话。
        
        Returns:
            requests.Session: 配置好的会话对象
        """
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
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
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        })
        
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
            'retries': self.max_retries,
            'socket_timeout': self.timeout,
        }
        
        if self.proxy:
            self.yt_dlp_opts['proxy'] = self.proxy
            
        # 添加Cookie支持
        cookies = self.cookie_manager.get_cookies(self.platform)
        if cookies:
            self.yt_dlp_opts['cookiefile'] = str(self.cookie_manager.cookie_dir / f"{self.platform}.json")
            
    def _yt_dlp_progress_hook(self, d: Dict[str, Any]):
        """yt-dlp进度回调。
        
        Args:
            d: 进度信息字典
        """
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                progress = downloaded / total
                self.update_progress(progress, f"正在下载: {d.get('filename', '')}")
        elif d['status'] == 'finished':
            self.update_progress(1.0, "下载完成")
            
    def download(
        self,
        url: str,
        save_path: Optional[Path] = None,
        **kwargs
    ) -> bool:
        """下载文件。
        
        默认使用yt-dlp下载器。子类可以重写此方法实现自定义下载逻辑。
        
        Args:
            url: 下载URL
            save_path: 保存路径
            **kwargs: 其他参数
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            DownloadError: 下载失败
        """
        try:
            with log_lock:
                logger.info(f"开始下载: {url}")
                
            if save_path:
                self.yt_dlp_opts['outtmpl'] = str(save_path)
                
            # 更新配置
            opts = self.yt_dlp_opts.copy()
            opts.update(kwargs)
            
            # 开始下载
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
                
            return True
            
        except Exception as e:
            with log_lock:
                logger.error(f"下载失败: {str(e)}")
            raise DownloadError(f"下载失败: {str(e)}")
            
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