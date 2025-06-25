#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
下载器基类模块。

该模块定义了所有下载器必须实现的基本接口。
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional

# 配置日志
logger = logging.getLogger(__name__)

class BaseDownloader(ABC):
    """下载器抽象基类。
    
    所有具体的下载器实现都应该继承这个基类并实现其抽象方法。
    
    Attributes:
        proxy: Optional[str], 代理服务器地址，格式为"host:port"
        timeout: float, 网络请求超时时间（秒）
    """
    
    def __init__(self, proxy: Optional[str] = None, timeout: float = 30.0) -> None:
        """初始化下载器。

        Args:
            proxy: 可选的代理服务器地址，格式为"host:port"
            timeout: 网络请求超时时间，默认30秒
        """
        self.proxy = proxy
        self.timeout = timeout
        logger.info(f"初始化下载器，代理：{proxy}，超时：{timeout}秒")

    @abstractmethod
    def download(self, url: str, save_path: Path) -> bool:
        """下载指定URL的视频到指定路径。

        Args:
            url: 要下载的视频URL
            save_path: 保存文件的路径

        Returns:
            bool: 下载是否成功

        Raises:
            ValueError: URL格式无效
            ConnectionError: 网络连接错误
            TimeoutError: 下载超时
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