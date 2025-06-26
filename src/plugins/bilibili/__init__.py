"""B站插件包。"""

from .extractor import BilibiliExtractor
from .sign import generate_sign

__all__ = ['BilibiliExtractor', 'generate_sign'] 