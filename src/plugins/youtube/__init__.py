"""YouTube下载器插件。

提供YouTube视频信息提取和下载功能。
"""

from .downloader import YouTubeDownloader

__version__ = "1.0.0"
__all__ = ["YouTubeDownloader"]

# 插件信息
PLUGIN_NAME = "youtube"
PLUGIN_DESCRIPTION = "YouTube视频下载器"
PLUGIN_AUTHOR = "Your Name"
PLUGIN_VERSION = __version__ 