"""xvideos 平台插件。

提供 xvideos 平台的视频下载和信息提取功能。
"""

from .downloader import XvideosDownloader
from .extractor import XvideosExtractor

__all__ = ['XvideosDownloader', 'XvideosExtractor'] 