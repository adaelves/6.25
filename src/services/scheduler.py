"""下载调度器模块。

提供优先级下载队列功能。
支持多优先级任务调度。
"""

import heapq
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class DownloadTask:
    """下载任务。
    
    Attributes:
        url: str, 下载URL
        priority: int, 优先级(0=最高,1=普通,2=后台)
        create_time: datetime, 创建时间
        start_time: Optional[datetime], 开始时间
        end_time: Optional[datetime], 结束时间
        status: str, 任务状态
        error: Optional[str], 错误信息
    """
    url: str
    priority: int
    create_time: datetime = datetime.now()
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = "pending"  # pending/running/completed/failed
    error: Optional[str] = None
    
    def __lt__(self, other: "DownloadTask") -> bool:
        """优先级比较。"""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.create_time < other.create_time

class DownloadScheduler:
    """下载调度器。
    
    支持优先级队列和并发控制。
    
    Attributes:
        _queue: List[DownloadTask], 任务队列
        _running: Dict[str, DownloadTask], 运行中的任务
        _completed: Dict[str, DownloadTask], 已完成的任务
        _failed: Dict[str, DownloadTask], 失败的任务
        _max_concurrent: int, 最大并发数
        _semaphore: asyncio.Semaphore, 并发控制信号量
    """
    
    def __init__(self, max_concurrent: int = 3):
        """初始化调度器。
        
        Args:
            max_concurrent: 最大并发数
        """
        self._queue: List[Tuple[int, datetime, str]] = []  # (priority, create_time, url)
        self._tasks: Dict[str, DownloadTask] = {}  # url -> task
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
    def add_task(self, url: str, priority: int = 1) -> DownloadTask:
        """添加下载任务。
        
        Args:
            url: 下载URL
            priority: 优先级(0=最高,1=普通,2=后台)
            
        Returns:
            DownloadTask: 下载任务
            
        Raises:
            ValueError: 优先级无效
        """
        if priority not in (0, 1, 2):
            raise ValueError(f"无效的优先级: {priority}")
            
        # 创建任务
        task = DownloadTask(url=url, priority=priority)
        self._tasks[url] = task
        
        # 加入队列
        heapq.heappush(self._queue, (priority, task.create_time, url))
        
        logger.info(f"添加下载任务: {url} (优先级={priority})")
        return task
        
    def get_task(self, url: str) -> Optional[DownloadTask]:
        """获取任务信息。
        
        Args:
            url: 下载URL
            
        Returns:
            Optional[DownloadTask]: 任务信息
        """
        return self._tasks.get(url)
        
    def get_next_task(self) -> Optional[DownloadTask]:
        """获取下一个任务。
        
        Returns:
            Optional[DownloadTask]: 下一个任务
        """
        while self._queue:
            _, _, url = heapq.heappop(self._queue)
            task = self._tasks[url]
            if task.status == "pending":
                return task
        return None
        
    async def run_task(self, task: DownloadTask, download_func: Any) -> None:
        """运行下载任务。
        
        Args:
            task: 下载任务
            download_func: 下载函数
        """
        async with self._semaphore:
            try:
                # 更新状态
                task.status = "running"
                task.start_time = datetime.now()
                
                # 执行下载
                await download_func(task.url)
                
                # 更新状态
                task.status = "completed"
                task.end_time = datetime.now()
                
                logger.info(f"下载完成: {task.url}")
                
            except Exception as e:
                # 更新状态
                task.status = "failed"
                task.end_time = datetime.now()
                task.error = str(e)
                
                logger.error(f"下载失败: {task.url} - {e}")
                
    async def run(self, download_func: Any) -> None:
        """运行调度器。
        
        Args:
            download_func: 下载函数
        """
        while True:
            task = self.get_next_task()
            if not task:
                await asyncio.sleep(1)
                continue
                
            asyncio.create_task(self.run_task(task, download_func))
            
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息。
        
        Returns:
            Dict[str, int]: 统计信息
        """
        stats = {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0
        }
        
        for task in self._tasks.values():
            stats[task.status] += 1
            
        return stats 