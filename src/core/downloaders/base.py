from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path
import logging

from ..task import DownloadTask, TaskStatus

logger = logging.getLogger(__name__)

class BaseDownloader(ABC):
    """下载器基类。"""
    
    def __init__(self, task: DownloadTask):
        """初始化下载器。
        
        Args:
            task: 下载任务
        """
        self.task = task
        self._stop = False
        self._paused = False
        
    @abstractmethod
    def start(self):
        """开始下载。"""
        pass
        
    def pause(self):
        """暂停下载。"""
        self._paused = True
        
    def resume(self):
        """恢复下载。"""
        self._paused = False
        
    def cancel(self):
        """取消下载。"""
        self._stop = True
        
    def _update_progress(self, progress: float):
        """更新进度。
        
        Args:
            progress: 进度值（0-100）
        """
        self.task.progress = progress
        
    def _update_speed(self, speed: float):
        """更新速度。
        
        Args:
            speed: 速度值（字节/秒）
        """
        self.task.speed = speed
        
    def _on_complete(self):
        """下载完成回调。"""
        self.task.status = TaskStatus.COMPLETED
        self.task.progress = 100
        self.task.speed = 0
        
    def _on_error(self, error: str):
        """下载错误回调。
        
        Args:
            error: 错误信息
        """
        self.task.status = TaskStatus.FAILED
        self.task.error = error
        self.task.speed = 0
        
    def _get_save_path(self, filename: Optional[str] = None) -> Path:
        """获取保存路径。
        
        Args:
            filename: 文件名
            
        Returns:
            Path: 保存路径
        """
        save_path = self.task.save_path
        
        if filename:
            save_path = save_path / filename
            
        # 创建目录
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        return save_path 