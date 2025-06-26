"""核心包。

提供基础功能和通用组件。
"""

from .exceptions import DownloadError, DownloadCanceled
from .downloader import BaseDownloader

__all__ = ['DownloadError', 'DownloadCanceled', 'BaseDownloader'] 