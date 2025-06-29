"""tumblr 平台插件。

提供 tumblr 平台的视频、图片下载和信息提取功能。
"""

from .downloader import TumblrDownloader
from .extractor import TumblrExtractor

__all__ = ['TumblrDownloader', 'TumblrExtractor'] 