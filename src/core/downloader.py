#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
下载器基类模块。

定义下载器的基本接口和通用功能。
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
from pathlib import Path

from .exceptions import DownloadCanceled

# 配置日志
logger = logging.getLogger(__name__)

class BaseDownloader(ABC):
    """基础下载器类。
    
    所有下载器的基类，定义了基本的下载接口。
    
    Attributes:
        save_dir: str, 保存目录
        progress_callback: Optional[Callable], 进度回调函数
    """
    
    def __init__(
        self,
        save_dir: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ):
        """初始化下载器。
        
        Args:
            save_dir: 保存目录
            progress_callback: 进度回调函数，接收进度(0-1)和状态信息
        """
        self.save_dir = Path(save_dir)
        self.progress_callback = progress_callback
        self.is_canceled = False
        
        # 创建保存目录
        os.makedirs(self.save_dir, exist_ok=True)
        
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
            
    def update_progress(self, progress: float, status: str = ""):
        """更新下载进度。
        
        Args:
            progress: 进度值(0-1)
            status: 状态信息
        """
        if self.progress_callback:
            self.progress_callback(progress, status)
            
    @abstractmethod
    async def download(self, url: str, save_path: Optional[Path] = None) -> bool:
        """下载资源。
        
        Args:
            url: 资源URL
            save_path: 可选的保存路径
            
        Returns:
            bool: 是否下载成功
        """
        pass

    @abstractmethod
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
        pass

    def _validate_url(self, url: str) -> bool:
        """验证URL格式是否有效。

        Args:
            url: 要验证的URL

        Returns:
            bool: URL是否有效
        """
        # TODO: 实现URL验证逻辑
        return True 