"""YouTube视频下载插件。

该插件提供YouTube视频下载功能。
"""

from .extractor import YouTubeExtractor
from .downloader import YouTubeDownloader

__version__ = "1.0.0"
__all__ = ['YouTubeExtractor', 'YouTubeDownloader']

# 插件信息
PLUGIN_NAME = "youtube"
PLUGIN_DESCRIPTION = "YouTube视频下载器"
PLUGIN_AUTHOR = "Your Name"
PLUGIN_VERSION = __version__ 