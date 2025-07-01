"""下载任务模块。

管理单个下载任务的状态和信息。
"""

from enum import Enum
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import uuid

class TaskStatus(Enum):
    """任务状态枚举。"""
    WAITING = "等待中"      # 等待下载
    DOWNLOADING = "下载中"  # 正在下载
    PAUSED = "已暂停"      # 暂停下载
    COMPLETED = "已完成"    # 下载完成
    FAILED = "下载失败"     # 下载失败
    CANCELED = "已取消"     # 已取消

class DownloadTask:
    """下载任务类。
    
    管理单个下载任务的所有信息，包括：
    - 基本信息（ID、URL、保存路径等）
    - 下载状态（等待、下载中、暂停等）
    - 进度信息（大小、速度、剩余时间等）
    - 错误信息
    
    Attributes:
        id: str, 任务唯一标识
        url: str, 下载URL
        save_path: Path, 保存路径
        platform: str, 平台标识
        create_time: datetime, 创建时间
        status: TaskStatus, 任务状态
        title: str, 视频标题
        total_size: int, 总大小(字节)
        downloaded_size: int, 已下载大小(字节)
        download_speed: float, 下载速度(字节/秒)
        progress: float, 下载进度(0-1)
        eta: int, 预计剩余时间(秒)
        error: Optional[str], 错误信息
    """
    
    def __init__(
        self,
        url: str,
        save_path: Path,
        platform: str,
        title: str = "",
        total_size: int = 0
    ):
        """初始化下载任务。
        
        Args:
            url: 下载URL
            save_path: 保存路径
            platform: 平台标识
            title: 视频标题(可选)
            total_size: 总大小(可选)
        """
        self.id = str(uuid.uuid4())
        self.url = url
        self.save_path = save_path
        self.platform = platform
        self.create_time = datetime.now()
        self.status = TaskStatus.WAITING
        
        self.title = title
        self.total_size = total_size
        self.downloaded_size = 0
        self.download_speed = 0.0
        self.progress = 0.0
        self.eta = 0
        self.error = None
        
        # 额外信息
        self.extra: Dict[str, Any] = {}
        
    def update(
        self,
        downloaded_size: Optional[int] = None,
        download_speed: Optional[float] = None,
        progress: Optional[float] = None,
        eta: Optional[int] = None,
        status: Optional[TaskStatus] = None,
        error: Optional[str] = None
    ) -> None:
        """更新任务信息。
        
        Args:
            downloaded_size: 已下载大小
            download_speed: 下载速度
            progress: 下载进度
            eta: 预计剩余时间
            status: 任务状态
            error: 错误信息
        """
        if downloaded_size is not None:
            self.downloaded_size = downloaded_size
        if download_speed is not None:
            self.download_speed = download_speed
        if progress is not None:
            self.progress = progress
        if eta is not None:
            self.eta = eta
        if status is not None:
            self.status = status
        if error is not None:
            self.error = error
            
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式。
        
        Returns:
            Dict[str, Any]: 任务信息字典
        """
        return {
            'id': self.id,
            'url': self.url,
            'save_path': str(self.save_path),
            'platform': self.platform,
            'create_time': self.create_time.isoformat(),
            'status': self.status.value,
            'title': self.title,
            'total_size': self.total_size,
            'downloaded_size': self.downloaded_size,
            'download_speed': self.download_speed,
            'progress': self.progress,
            'eta': self.eta,
            'error': self.error,
            'extra': self.extra
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DownloadTask':
        """从字典创建任务实例。
        
        Args:
            data: 任务信息字典
            
        Returns:
            DownloadTask: 任务实例
        """
        task = cls(
            url=data['url'],
            save_path=Path(data['save_path']),
            platform=data['platform'],
            title=data.get('title', ''),
            total_size=data.get('total_size', 0)
        )
        task.id = data['id']
        task.create_time = datetime.fromisoformat(data['create_time'])
        task.status = TaskStatus(data['status'])
        task.downloaded_size = data.get('downloaded_size', 0)
        task.download_speed = data.get('download_speed', 0.0)
        task.progress = data.get('progress', 0.0)
        task.eta = data.get('eta', 0)
        task.error = data.get('error')
        task.extra = data.get('extra', {})
        return task 