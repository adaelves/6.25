"""YouTube视频下载器模块。

该模块实现了YouTube视频的下载功能。
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import yt_dlp
from core.downloader import BaseDownloader
from services.proxy import get_current_proxy
from .extractor import YouTubeExtractor

logger = logging.getLogger(__name__)

class YouTubeDownloader(BaseDownloader):
    """YouTube视频下载器。
    
    继承自BaseDownloader，使用yt-dlp实现YouTube视频下载。
    """
    
    def __init__(self, proxy: Optional[str] = None, timeout: float = 30.0):
        """初始化下载器。
        
        Args:
            proxy: 可选的代理服务器地址
            timeout: 网络请求超时时间（秒）
        """
        # 如果没有指定代理，使用代理管理器
        if proxy is None:
            proxy = get_current_proxy()
            
        super().__init__(proxy=proxy, timeout=timeout)
        self.extractor = YouTubeExtractor(proxy=proxy, timeout=timeout)
        
        # 用于进度显示
        self._last_progress = 0
        self._progress_output = sys.stderr
        
    def download(self, url: str, save_path: Path) -> bool:
        """下载YouTube视频。
        
        Args:
            url: YouTube视频URL
            save_path: 保存路径
            
        Returns:
            bool: 下载是否成功
            
        Raises:
            ValueError: URL无效
            ConnectionError: 网络连接错误
            TimeoutError: 下载超时
        """
        try:
            if not self._validate_url(url):
                raise ValueError(f"无效的YouTube URL: {url}")
                
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': str(save_path),
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [self._progress_hook],
            }
            
            # 使用代理
            if self.proxy:
                logger.info(f"使用代理: {self.proxy}")
                ydl_opts['proxy'] = self.proxy
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except yt_dlp.utils.DownloadError as e:
                    if "HTTP Error 403: Forbidden" in str(e) and self.proxy:
                        logger.warning("代理访问被拒绝，尝试切换代理...")
                        new_proxy = get_current_proxy()
                        if new_proxy and new_proxy != self.proxy:
                            self.proxy = new_proxy
                            ydl_opts['proxy'] = self.proxy
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                                ydl2.download([url])
                        else:
                            raise
                    else:
                        raise
                
            # 完成下载，清理进度显示
            print(file=self._progress_output)
            return True
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            return False
            
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息。
        
        Args:
            url: YouTube视频URL
            
        Returns:
            Dict[str, Any]: 视频信息字典
            
        Raises:
            ValueError: URL无效
            ConnectionError: 网络连接错误
            TimeoutError: 请求超时
        """
        return self.extractor.extract_info(url)
        
    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """下载进度回调。
        
        Args:
            d: 进度信息字典
        """
        if d['status'] == 'downloading':
            total = d.get('total_bytes')
            downloaded = d.get('downloaded_bytes', 0)
            
            if total:
                progress = (downloaded / total) * 100
                # 只有进度变化超过0.1%时才更新显示
                if abs(progress - self._last_progress) >= 0.1:
                    self._last_progress = progress
                    speed = d.get('speed', 0)
                    if speed:
                        speed_str = f"{speed/1024/1024:.1f} MB/s"
                    else:
                        speed_str = "N/A"
                    
                    progress_str = f"\r下载进度: {progress:.1f}% | 速度: {speed_str}"
                    print(progress_str, end='', file=self._progress_output)
                    self._progress_output.flush()
                    
        elif d['status'] == 'finished':
            print("\r下载完成: 100%", end='', file=self._progress_output)
            self._progress_output.flush() 