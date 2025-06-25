"""YouTube视频信息提取模块。

该模块负责从YouTube视频URL中提取视频信息。
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import yt_dlp

logger = logging.getLogger(__name__)

class YouTubeExtractor:
    """YouTube视频信息提取器。
    
    使用yt-dlp库从YouTube视频中提取信息。
    
    Attributes:
        proxy: Optional[str], 代理服务器地址
        timeout: float, 网络请求超时时间（秒）
    """
    
    def __init__(self, proxy: Optional[str] = None, timeout: float = 30.0):
        """初始化提取器。
        
        Args:
            proxy: 可选的代理服务器地址
            timeout: 网络请求超时时间
        """
        self.proxy = proxy
        self.timeout = timeout
        
        # yt-dlp配置
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        if proxy:
            self.ydl_opts['proxy'] = proxy
            
    def extract_info(self, url: str) -> Dict[str, Any]:
        """提取视频信息。
        
        Args:
            url: YouTube视频URL
            
        Returns:
            Dict[str, Any]: 包含视频信息的字典，包括：
                - title: str, 视频标题
                - author: str, 作者
                - quality: List[str], 可用的视频质量列表
                - view_count: int, 播放量
                - like_count: int, 点赞数
                - duration: int, 视频时长（秒）
                
        Raises:
            ValueError: URL无效
            ConnectionError: 网络连接错误
            TimeoutError: 请求超时
        """
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # 处理年龄限制视频
                if info.get('age_limit', 0) > 0:
                    logger.warning(f"视频有年龄限制: {url}")
                    self.ydl_opts['age_limit'] = 25
                    with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                
                return {
                    'title': info.get('title', ''),
                    'author': info.get('uploader', ''),
                    'quality': [f'{fmt["height"]}p' for fmt in info.get('formats', [])
                              if fmt.get('height')],
                    'view_count': info.get('view_count', 0),
                    'like_count': info.get('like_count', 0),
                    'duration': info.get('duration', 0)
                }
                
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"提取信息失败: {e}")
            raise ValueError(f"无法提取视频信息: {e}")
        except Exception as e:
            logger.error(f"未知错误: {e}")
            raise 