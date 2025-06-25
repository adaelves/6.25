"""B站视频下载插件。

提供B站视频信息提取和下载功能。
"""

from .extractor import BilibiliExtractor
from .sign import generate_sign

__all__ = ['BilibiliExtractor', 'generate_sign'] 