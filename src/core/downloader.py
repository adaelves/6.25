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
from typing import Optional, Dict, Any, Callable, Union
from pathlib import Path
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

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
    
    Attributes:
        platform: str, 平台标识
        save_dir: Path, 保存目录
        progress_callback: Optional[Callable[[float, str], None]], 进度回调函数
        session: requests.Session, 会话对象
        proxy: Optional[str], 代理地址
        timeout: int, 超时时间(秒)
        max_retries: int, 最大重试次数
        cookie_manager: CookieManager, Cookie管理器
    """
    
    def __init__(
        self,
        platform: str,
        save_dir: Union[str, Path],
        progress_callback: Optional[Callable[[float, str], None]] = None,
        proxy: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3,
        cookie_manager: Optional[CookieManager] = None
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
        """
        self.platform = platform
        self.save_dir = Path(save_dir)
        self.progress_callback = progress_callback
        self.proxy = proxy
        self.timeout = timeout
        self.max_retries = max_retries
        self.is_canceled = False
        
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
            
    def download(
        self,
        url: str,
        save_path: Optional[Path] = None,
        **kwargs
    ) -> bool:
        """下载文件。
        
        Args:
            url: 下载URL
            save_path: 保存路径
            **kwargs: 其他参数
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            DownloadError: 下载失败
        """
        raise NotImplementedError("子类必须实现download方法")

    def close(self):
        """关闭下载器。"""
        if self.session:
            self.session.close()
            with log_lock:
                logger.info("下载器已关闭")

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息。

        Args:
            url: 视频URL

        Returns:
            Dict[str, Any]: 包含视频信息的字典，必须包含以下键：
                - title: str, 视频标题
                - author: str, 作者
                - quality: str, 视频质量
                
        Raises:
            ValueError: URL格式无效
            ConnectionError: 网络连接错误
            TimeoutError: 请求超时
        """
        with log_lock:
            logger.info(f"获取视频信息: {url}")
            
        return {
            "title": "",
            "author": "",
            "quality": ""
        }

    def _validate_url(self, url: str) -> bool:
        """验证URL格式是否有效。

        Args:
            url: 要验证的URL

        Returns:
            bool: URL是否有效
        """
        # TODO: 实现URL验证逻辑
        return True 