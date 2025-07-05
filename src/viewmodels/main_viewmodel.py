from typing import Optional
from PySide6.QtCore import QObject, Signal, Slot
from src.models.downloader import VideoDownloader
from src.models.settings import Settings

class MainViewModel(QObject):
    """主窗口视图模型类"""
    
    # 信号定义
    download_progress = Signal(str, int)  # 视频ID, 进度
    download_speed = Signal(int, int)  # 速度(KB/s), 剩余时间(s)
    download_error = Signal(str, str)  # 视频ID, 错误信息
    download_complete = Signal(str)  # 视频ID
    
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings()
        self.downloader = VideoDownloader()
        
        # 连接下载器信号
        self.downloader.progress_updated.connect(self._on_progress)
        self.downloader.speed_updated.connect(self._on_speed)
        self.downloader.download_error.connect(self._on_error)
        self.downloader.download_complete.connect(self._on_complete)
    
    @Slot(str, str, str)
    def start_download(self, url: str, format: str, quality: str) -> None:
        """开始下载任务
        
        Args:
            url: 视频URL
            format: 下载格式
            quality: 视频质量
        """
        try:
            self.downloader.download(
                url,
                format=format,
                quality=quality,
                save_path=self.settings.download_path,
                proxy=self.settings.proxy if self.settings.use_proxy else None,
                max_threads=self.settings.max_threads
            )
        except Exception as e:
            self.download_error.emit(url, str(e))
    
    @Slot(str)
    def update_download_path(self, path: str) -> None:
        """更新下载路径
        
        Args:
            path: 新的下载路径
        """
        self.settings.download_path = path
        self.settings.save()
    
    @Slot(str, int)
    def _on_progress(self, video_id: str, progress: int) -> None:
        """下载进度更新处理
        
        Args:
            video_id: 视频ID
            progress: 进度百分比
        """
        self.download_progress.emit(video_id, progress)
    
    @Slot(int, int)
    def _on_speed(self, speed: int, remaining: int) -> None:
        """下载速度更新处理
        
        Args:
            speed: 下载速度(KB/s)
            remaining: 剩余时间(秒)
        """
        self.download_speed.emit(speed, remaining)
    
    @Slot(str, str)
    def _on_error(self, video_id: str, error: str) -> None:
        """下载错误处理
        
        Args:
            video_id: 视频ID
            error: 错误信息
        """
        self.download_error.emit(video_id, error)
    
    @Slot(str)
    def _on_complete(self, video_id: str) -> None:
        """下载完成处理
        
        Args:
            video_id: 视频ID
        """
        self.download_complete.emit(video_id) 