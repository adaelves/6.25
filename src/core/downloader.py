#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
下载器基类模块。

定义下载器的基本接口和通用功能。
"""

import os
import logging
from typing import Optional, Dict, Any, Callable, Union
from pathlib import Path
import json
import time

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .exceptions import DownloadCanceled

# 配置日志
logger = logging.getLogger(__name__)

class DownloadError(Exception):
    """下载错误。"""
    pass

class BaseDownloader:
    """下载器基类。
    
    提供基本的下载功能和进度回调机制。
    
    Attributes:
        save_dir: str, 保存目录
        progress_callback: Optional[Callable[[float, str], None]], 进度回调函数
        session: requests.Session, 会话对象
        proxy: Optional[str], 代理地址
        timeout: int, 超时时间(秒)
        max_retries: int, 最大重试次数
    """
    
    def __init__(
        self,
        save_dir: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        proxy: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3
    ):
        """初始化下载器。
        
        Args:
            save_dir: 保存目录
            progress_callback: 进度回调函数，接收进度(0-1)和状态消息
            proxy: 代理地址(如"http://127.0.0.1:1080")
            timeout: 超时时间(秒)
            max_retries: 最大重试次数
        """
        self.save_dir = Path(save_dir)
        self.progress_callback = progress_callback
        self.is_canceled = False
        
        # 创建保存目录
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建会话
        self.session = self._create_session(proxy, timeout, max_retries)
        
    def _create_session(self, proxy: Optional[str], timeout: int, max_retries: int) -> requests.Session:
        """创建会话。
        
        配置代理和重试策略。
        
        Returns:
            requests.Session: 会话对象
        """
        session = requests.Session()
        
        # 配置代理
        if proxy:
            session.proxies = {
                "http": proxy,
                "https": proxy
            }
            
        # 配置重试
        retry_strategy = Retry(
            total=max_retries,  # 最大重试次数
            backoff_factor=1,  # 重试等待时间 = {backoff_factor} * (2 ** ({retry_number} - 1))
            status_forcelist=[500, 502, 503, 504]  # 需要重试的HTTP状态码
        )
        
        # 配置适配器
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置。
        
        从config.json加载配置。
        
        Returns:
            Dict[str, Any]: 配置字典
            
        Raises:
            DownloadError: 配置加载失败
        """
        try:
            config_path = Path("configs/config.json")
            if not config_path.exists():
                return {}
                
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return {}
            
    def cancel(self):
        """取消下载。"""
        self.is_canceled = True
        
    def check_canceled(self):
        """检查是否已取消。
        
        Raises:
            DownloadCanceled: 如果下载已被取消
        """
        if self.is_canceled:
            raise DownloadCanceled("下载已取消")
            
    def update_progress(self, progress: float, status: str) -> None:
        """更新下载进度。
        
        Args:
            progress: 进度值（0-1）
            status: 状态消息
        """
        if self.progress_callback:
            self.progress_callback(progress, status)
            
    def download(
        self,
        url: str,
        save_path: Union[str, Path],
        chunk_size: int = 8192,
        **kwargs
    ) -> bool:
        """下载文件。
        
        Args:
            url: 下载URL
            save_path: 保存路径
            chunk_size: 分块大小(字节)
            **kwargs: 其他参数
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            DownloadError: 下载失败
        """
        try:
            # 创建保存目录
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 发送请求
            response = self.session.get(
                url,
                stream=True,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            
            # 保存文件
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        
            return True
            
        except requests.Timeout:
            logger.error(f"下载超时: {url}")
            raise DownloadError(f"下载超时: {url}")
            
        except requests.RequestException as e:
            logger.error(f"下载失败: {url} - {e}")
            raise DownloadError(f"下载失败: {url} - {e}")
            
        except Exception as e:
            logger.error(f"下载出错: {url} - {e}")
            raise DownloadError(f"下载出错: {url} - {e}")
            
    def close(self):
        """关闭下载器。"""
        if self.session:
            self.session.close()

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