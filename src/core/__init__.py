"""核心模块包。

提供下载器的核心功能。
"""

from .exceptions import DownloadError, DownloadCanceled
from .downloader import BaseDownloader

__all__ = ['DownloadError', 'DownloadCanceled', 'BaseDownloader'] 