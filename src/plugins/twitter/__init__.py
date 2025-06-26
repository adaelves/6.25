"""Twitter插件包。

提供Twitter平台的视频提取功能。
"""

from .extractor import TwitterExtractor
from .downloader import TwitterDownloader
from .config import TwitterDownloaderConfig

__all__ = ['TwitterExtractor', 'TwitterDownloader', 'TwitterDownloaderConfig'] 