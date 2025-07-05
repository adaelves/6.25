import os
import asyncio
import aiohttp
from typing import Optional, Dict
from urllib.parse import urlparse
from PySide6.QtCore import QObject, Signal
import yt_dlp

class VideoDownloader(QObject):
    """视频下载器类"""
    
    # 信号定义
    progress_updated = Signal(str, int)  # 视频ID, 进度
    speed_updated = Signal(int, int)  # 速度(KB/s), 剩余时间(s)
    download_error = Signal(str, str)  # 视频ID, 错误信息
    download_complete = Signal(str)  # 视频ID
    
    def __init__(self) -> None:
        super().__init__()
        self._tasks: Dict[str, asyncio.Task] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        
    def download(
        self,
        url: str,
        format: str = "mp4",
        quality: str = "best",
        save_path: str = "downloads",
        proxy: Optional[str] = None,
        max_threads: int = 4
    ) -> None:
        """开始下载视频
        
        Args:
            url: 视频URL
            format: 下载格式
            quality: 视频质量
            save_path: 保存路径
            proxy: 代理地址
            max_threads: 最大线程数
        """
        # 确保保存目录存在
        os.makedirs(save_path, exist_ok=True)
        
        # 配置yt-dlp选项
        ydl_opts = {
            'format': self._get_format_string(format, quality),
            'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
            'progress_hooks': [self._progress_hook],
            'proxy': proxy,
            'max_downloads': 1,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        # 启动下载任务
        video_id = self._get_video_id(url)
        task = asyncio.create_task(self._download_async(url, ydl_opts))
        self._tasks[video_id] = task
        
    async def _download_async(self, url: str, opts: dict) -> None:
        """异步下载视频
        
        Args:
            url: 视频URL
            opts: yt-dlp选项
        """
        video_id = self._get_video_id(url)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ydl.download([url])
                )
            self.download_complete.emit(video_id)
        except Exception as e:
            self.download_error.emit(video_id, str(e))
        finally:
            if video_id in self._tasks:
                del self._tasks[video_id]
                
    def _progress_hook(self, d: dict) -> None:
        """下载进度回调
        
        Args:
            d: 进度信息字典
        """
        if d['status'] == 'downloading':
            # 计算下载进度
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                progress = int(downloaded * 100 / total)
                self.progress_updated.emit(d['filename'], progress)
            
            # 计算下载速度和剩余时间
            speed = d.get('speed', 0)
            if speed:
                speed_kb = int(speed / 1024)
                eta = d.get('eta', 0)
                self.speed_updated.emit(speed_kb, eta)
                
    def _get_format_string(self, format: str, quality: str) -> str:
        """获取格式字符串
        
        Args:
            format: 下载格式
            quality: 视频质量
            
        Returns:
            str: yt-dlp格式字符串
        """
        if format.lower() == 'mp3':
            return 'bestaudio[ext=m4a]/bestaudio/best'
            
        quality_map = {
            '最高质量': 'bestvideo+bestaudio/best',
            '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]'
        }
        return quality_map.get(quality, 'bestvideo+bestaudio/best')
        
    def _get_video_id(self, url: str) -> str:
        """从URL获取视频ID
        
        Args:
            url: 视频URL
            
        Returns:
            str: 视频ID
        """
        parsed = urlparse(url)
        return parsed.path.split('/')[-1] or url 