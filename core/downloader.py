"""下载功能实现模块"""

from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging
import time
from datetime import datetime
import yt_dlp
from PySide6.QtCore import QThread, Signal, QObject

from .models import VideoInfo, DownloadHistory
from .database import DatabaseManager

class DownloadStatus(Enum):
    """下载状态枚举"""
    WAITING = "waiting"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class DownloadTask:
    """下载任务数据类"""
    url: str
    title: str
    save_path: str
    status: DownloadStatus = DownloadStatus.WAITING
    progress: float = 0.0
    speed: float = 0.0
    error_msg: Optional[str] = None
    video_info: Optional[VideoInfo] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class DownloadWorker(QThread):
    """下载工作线程"""
    progress_updated = Signal(str, float, float)  # task_id, progress, speed
    status_changed = Signal(str, DownloadStatus)  # task_id, status
    download_finished = Signal(str, bool, str)  # task_id, success, error_msg
    
    def __init__(self, task: DownloadTask, parent=None):
        super().__init__(parent)
        self.task = task
        self.is_paused = False
        self.is_cancelled = False
    
    def run(self):
        """执行下载任务"""
        try:
            self.task.start_time = datetime.now()
            self.task.status = DownloadStatus.DOWNLOADING
            self.status_changed.emit(self.task.url, self.task.status)
            
            def progress_hook(d):
                if d['status'] == 'downloading':
                    # 更新下载进度
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    if total > 0:
                        progress = (downloaded / total) * 100
                        speed = d.get('speed', 0)
                        self.progress_updated.emit(self.task.url, progress, speed)
                
                elif d['status'] == 'finished':
                    # 下载完成
                    self.task.status = DownloadStatus.COMPLETED
                    self.status_changed.emit(self.task.url, self.task.status)
            
            # 配置yt-dlp选项
            ydl_opts = {
                'format': 'best',
                'outtmpl': f'{self.task.save_path}/%(title)s.%(ext)s',
                'progress_hooks': [progress_hook],
                'noprogress': True,  # 禁用控制台进度条
            }
            
            # 执行下载
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.task.url])
            
            self.task.end_time = datetime.now()
            self.download_finished.emit(self.task.url, True, "")
            
        except Exception as e:
            self.task.status = DownloadStatus.ERROR
            self.task.error_msg = str(e)
            self.status_changed.emit(self.task.url, self.task.status)
            self.download_finished.emit(self.task.url, False, str(e))
    
    def pause(self):
        """暂停下载"""
        self.is_paused = True
        self.task.status = DownloadStatus.PAUSED
        self.status_changed.emit(self.task.url, self.task.status)
    
    def resume(self):
        """恢复下载"""
        self.is_paused = False
        self.task.status = DownloadStatus.DOWNLOADING
        self.status_changed.emit(self.task.url, self.task.status)
    
    def cancel(self):
        """取消下载"""
        self.is_cancelled = True
        self.task.status = DownloadStatus.ERROR
        self.task.error_msg = "Download cancelled"
        self.status_changed.emit(self.task.url, self.task.status)

class VideoDownloader(QObject):
    """视频下载器核心类"""
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("VideoDownloader")
        self.tasks: Dict[str, DownloadTask] = {}
        self.workers: Dict[str, DownloadWorker] = {}
        self.max_concurrent = 3
        self.db = DatabaseManager()
    
    def add_task(self, url: str, title: str, save_path: str) -> str:
        """添加下载任务"""
        task_id = url  # 简单使用URL作为任务ID
        if task_id in self.tasks:
            self.logger.warning(f"Task already exists: {url}")
            return task_id
            
        task = DownloadTask(url=url, title=title, save_path=save_path)
        self.tasks[task_id] = task
        self.logger.info(f"Added task: {title}")
        
        # 如果正在运行的任务数小于最大并发数，启动新任务
        if len(self.workers) < self.max_concurrent:
            self._start_task(task_id)
        
        return task_id
    
    def _start_task(self, task_id: str):
        """启动下载任务"""
        if task_id not in self.tasks:
            return
            
        task = self.tasks[task_id]
        worker = DownloadWorker(task)
        
        # 连接信号
        worker.progress_updated.connect(self._on_progress_updated)
        worker.status_changed.connect(self._on_status_changed)
        worker.download_finished.connect(self._on_download_finished)
        
        self.workers[task_id] = worker
        worker.start()
    
    def pause_task(self, task_id: str):
        """暂停下载任务"""
        if task_id in self.workers:
            self.workers[task_id].pause()
    
    def resume_task(self, task_id: str):
        """恢复下载任务"""
        if task_id in self.workers:
            self.workers[task_id].resume()
        elif task_id in self.tasks:
            if len(self.workers) < self.max_concurrent:
                self._start_task(task_id)
    
    def cancel_task(self, task_id: str):
        """取消下载任务"""
        if task_id in self.workers:
            self.workers[task_id].cancel()
            self.workers[task_id].wait()
            del self.workers[task_id]
        
        if task_id in self.tasks:
            del self.tasks[task_id]
    
    def _on_progress_updated(self, task_id: str, progress: float, speed: float):
        """处理进度更新"""
        if task_id in self.tasks:
            self.tasks[task_id].progress = progress
            self.tasks[task_id].speed = speed
    
    def _on_status_changed(self, task_id: str, status: DownloadStatus):
        """处理状态变化"""
        if task_id in self.tasks:
            self.tasks[task_id].status = status
    
    def _on_download_finished(self, task_id: str, success: bool, error_msg: str):
        """处理下载完成"""
        if task_id in self.workers:
            worker = self.workers[task_id]
            worker.wait()
            del self.workers[task_id]
        
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if success:
                # 保存下载历史
                if task.video_info and task.start_time and task.end_time:
                    history = DownloadHistory(
                        video=task.video_info,
                        download_time=task.end_time,
                        save_path=task.save_path,
                        file_size=0,  # TODO: 获取文件大小
                        duration=(task.end_time - task.start_time).seconds
                    )
                    self.db.add_download_history(history)
            else:
                task.error_msg = error_msg
            
            # 检查是否有等待的任务可以开始
            waiting_tasks = [
                tid for tid, t in self.tasks.items()
                if t.status == DownloadStatus.WAITING
            ]
            if waiting_tasks and len(self.workers) < self.max_concurrent:
                self._start_task(waiting_tasks[0]) 