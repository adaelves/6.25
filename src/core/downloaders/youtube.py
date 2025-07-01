import yt_dlp
import logging
from pathlib import Path
from typing import Optional

from .base import BaseDownloader
from ..task import DownloadTask

logger = logging.getLogger(__name__)

class YouTubeDownloader(BaseDownloader):
    """YouTube下载器。"""
    
    def __init__(self, task: DownloadTask):
        """初始化下载器。
        
        Args:
            task: 下载任务
        """
        super().__init__(task)
        self._downloader = None
        
    def start(self):
        """开始下载。"""
        try:
            # 创建下载选项
            options = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': str(self._get_save_path('%(title)s.%(ext)s')),
                'progress_hooks': [self._progress_hook],
                'quiet': True,
                'no_warnings': True
            }
            
            # 添加代理设置
            if self.task.settings.get('proxy.enabled'):
                proxy_type = self.task.settings.get('proxy.type', 'http').lower()
                proxy_host = self.task.settings.get('proxy.host', '127.0.0.1')
                proxy_port = self.task.settings.get('proxy.port', 7890)
                options['proxy'] = f'{proxy_type}://{proxy_host}:{proxy_port}'
            
            # 创建下载器
            self._downloader = yt_dlp.YoutubeDL(options)
            
            # 开始下载
            self._downloader.download([self.task.url])
            
            # 下载完成
            self._on_complete()
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            self._on_error(str(e))
            
    def _progress_hook(self, d: dict):
        """进度回调。
        
        Args:
            d: 进度信息
        """
        if d['status'] == 'downloading':
            # 更新进度
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            
            if total > 0:
                progress = downloaded / total * 100
                self._update_progress(progress)
            
            # 更新速度
            speed = d.get('speed', 0)
            if speed:
                self._update_speed(speed)
                
        elif d['status'] == 'finished':
            self._update_progress(100)
            self._update_speed(0) 