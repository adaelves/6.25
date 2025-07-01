from enum import Enum
from pathlib import Path
import uuid
import logging

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """任务状态。"""
    PENDING = 'pending'  # 等待下载
    DOWNLOADING = 'downloading'  # 下载中
    PAUSED = 'paused'  # 已暂停
    COMPLETED = 'completed'  # 已完成
    FAILED = 'failed'  # 下载失败
    CANCELED = 'canceled'  # 已取消

class DownloadTask:
    """下载任务。"""
    
    def __init__(self, url: str, save_path: Path, platform: str):
        """初始化任务。
        
        Args:
            url: 下载链接
            save_path: 保存路径
            platform: 平台名称
        """
        self.id = str(uuid.uuid4())
        self.url = url
        self.save_path = Path(save_path)
        self.platform = platform
        self.status = TaskStatus.PENDING
        self.progress = 0
        self.speed = 0
        self.error = None
        self._downloader = None
        
    def start(self):
        """开始下载。"""
        try:
            if self.status == TaskStatus.DOWNLOADING:
                return
                
            self.status = TaskStatus.DOWNLOADING
            self._create_downloader()
            self._downloader.start()
            
        except Exception as e:
            logger.error(f"开始下载失败: {e}")
            self.status = TaskStatus.FAILED
            self.error = str(e)
            
    def pause(self):
        """暂停下载。"""
        if self.status != TaskStatus.DOWNLOADING:
            return
            
        try:
            self._downloader.pause()
            self.status = TaskStatus.PAUSED
            
        except Exception as e:
            logger.error(f"暂停下载失败: {e}")
            
    def resume(self):
        """恢复下载。"""
        if self.status != TaskStatus.PAUSED:
            return
            
        try:
            self._downloader.resume()
            self.status = TaskStatus.DOWNLOADING
            
        except Exception as e:
            logger.error(f"恢复下载失败: {e}")
            
    def cancel(self):
        """取消下载。"""
        if self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED]:
            return
            
        try:
            if self._downloader:
                self._downloader.cancel()
            self.status = TaskStatus.CANCELED
            
        except Exception as e:
            logger.error(f"取消下载失败: {e}")
            
    def _create_downloader(self):
        """创建下载器。"""
        if self.platform == 'youtube':
            from .downloaders.youtube import YouTubeDownloader
            self._downloader = YouTubeDownloader(self)
        elif self.platform == 'twitter':
            from .downloaders.twitter import TwitterDownloader
            self._downloader = TwitterDownloader(self)
        elif self.platform == 'bilibili':
            from .downloaders.bilibili import BilibiliDownloader
            self._downloader = BilibiliDownloader(self)
        else:
            raise ValueError(f"不支持的平台: {self.platform}")
            
    @property
    def is_active(self) -> bool:
        """是否处于活动状态。"""
        return self.status in [TaskStatus.PENDING, TaskStatus.DOWNLOADING, TaskStatus.PAUSED]
        
    @property
    def is_completed(self) -> bool:
        """是否已完成。"""
        return self.status == TaskStatus.COMPLETED
        
    @property
    def is_failed(self) -> bool:
        """是否已失败。"""
        return self.status == TaskStatus.FAILED
        
    @property
    def is_canceled(self) -> bool:
        """是否已取消。"""
        return self.status == TaskStatus.CANCELED 