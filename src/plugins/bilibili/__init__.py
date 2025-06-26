"""哔哩哔哩插件包。

提供B站视频下载功能。"""

from .extractor import BilibiliExtractor
from .sign import WBIKeyManager

__all__ = ['BilibiliExtractor', 'WBIKeyManager'] 