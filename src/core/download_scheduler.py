"""下载调度器模块。

提供下载任务的调度、并发控制和性能优化。
"""

import os
import time
import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import threading
from queue import Queue, PriorityQueue
import hashlib
import hmac
from concurrent.futures import ThreadPoolExecutor

from .exceptions import DownloadError, NetworkError, AuthError
from .cache import Cache
from .cookie_manager import CookieManager

logger = logging.getLogger(__name__)

@dataclass
class DownloadTask:
    """下载任务。
    
    Attributes:
        id: 任务ID
        url: 下载URL
        save_path: 保存路径
        priority: 优先级(1-10，1最高)
        speed_limit: 速度限制(bytes/s)
        chunk_size: 块大小
        buffer_size: 缓冲区大小
        retries: 重试次数
        timeout: 超时时间
        headers: 请求头
        cookies: Cookie
        progress_callback: 进度回调
        status_callback: 状态回调
        created_at: 创建时间
        started_at: 开始时间
        finished_at: 完成时间
        total_size: 总大小
        downloaded_size: 已下载大小
        current_speed: 当前速度
        average_speed: 平均速度
        remaining_time: 剩余时间
        status: 状态
        error: 错误信息
    """
    
    id: str
    url: str
    save_path: Path
    priority: int = 5
    speed_limit: Optional[int] = None
    chunk_size: int = 8192
    buffer_size: int = 1024 * 1024
    retries: int = 3
    timeout: int = 30
    headers: Optional[Dict[str, str]] = None
    cookies: Optional[Dict[str, str]] = None
    progress_callback: Optional[Callable] = None
    status_callback: Optional[Callable] = None
    
    created_at: datetime = datetime.now()
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    total_size: int = 0
    downloaded_size: int = 0
    current_speed: int = 0
    average_speed: int = 0
    remaining_time: Optional[timedelta] = None
    
    status: str = "pending"  # pending, downloading, paused, completed, failed
    error: Optional[str] = None

class DownloadScheduler:
    """下载调度器。
    
    提供以下功能：
    1. 任务调度和并发控制
    2. 速度限制和流量控制
    3. 内存使用优化
    4. 缓存管理
    5. 安全性控制
    
    Attributes:
        max_concurrent: 最大并发数
        max_retries: 最大重试次数
        default_timeout: 默认超时时间
        cache: 缓存管理器
        cookie_manager: Cookie管理器
    """
    
    def __init__(
        self,
        max_concurrent: int = 3,
        max_retries: int = 3,
        default_timeout: int = 30,
        cache_dir: Optional[Path] = None,
        cookie_manager: Optional[CookieManager] = None,
        secret_key: Optional[str] = None
    ):
        """初始化下载调度器。
        
        Args:
            max_concurrent: 最大并发数
            max_retries: 最大重试次数
            default_timeout: 默认超时时间
            cache_dir: 缓存目录
            cookie_manager: Cookie管理器
            secret_key: 签名密钥
        """
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.default_timeout = default_timeout
        
        # 任务队列
        self._task_queue = PriorityQueue()
        self._active_tasks: Dict[str, DownloadTask] = {}
        self._completed_tasks: Dict[str, DownloadTask] = {}
        self._failed_tasks: Dict[str, DownloadTask] = {}
        
        # 线程池
        self._thread_pool = ThreadPoolExecutor(max_workers=max_concurrent)
        
        # 缓存管理器
        self.cache = Cache(cache_dir) if cache_dir else None
        
        # Cookie管理器
        self.cookie_manager = cookie_manager
        
        # 签名密钥
        self._secret_key = secret_key.encode() if secret_key else None
        
        # 状态
        self._running = False
        self._paused = False
        
        # 统计信息
        self.stats = {
            'total_tasks': 0,
            'active_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'total_downloaded': 0,
            'current_speed': 0,
            'average_speed': 0
        }
        
        # 启动调度器
        self._start()
        
    def _start(self):
        """启动调度器。"""
        self._running = True
        threading.Thread(target=self._schedule_loop, daemon=True).start()
        threading.Thread(target=self._stats_loop, daemon=True).start()
        
    def _schedule_loop(self):
        """调度循环。"""
        while self._running:
            if not self._paused and len(self._active_tasks) < self.max_concurrent:
                try:
                    # 获取优先级最高的任务
                    priority, task = self._task_queue.get_nowait()
                    
                    # 提交任务
                    self._thread_pool.submit(self._download_task, task)
                    
                    # 更新状态
                    self._active_tasks[task.id] = task
                    self.stats['active_tasks'] = len(self._active_tasks)
                    
                except Exception:
                    pass
                    
            time.sleep(0.1)
            
    def _stats_loop(self):
        """统计循环。"""
        while self._running:
            # 更新统计信息
            total_speed = 0
            for task in self._active_tasks.values():
                total_speed += task.current_speed
                
            self.stats['current_speed'] = total_speed
            self.stats['average_speed'] = (
                self.stats['total_downloaded'] /
                (time.time() - self.stats['start_time'])
                if self.stats.get('start_time') else 0
            )
            
            time.sleep(1)
            
    def _download_task(self, task: DownloadTask):
        """下载任务。
        
        Args:
            task: 下载任务
        """
        try:
            # 更新任务状态
            task.status = "downloading"
            task.started_at = datetime.now()
            
            # 创建保存目录
            task.save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 获取文件大小
            response = self._make_request(task.url, method="HEAD")
            task.total_size = int(response.headers.get('content-length', 0))
            
            # 下载文件
            with open(task.save_path, 'wb') as f:
                response = self._make_request(
                    task.url,
                    stream=True,
                    chunk_size=task.chunk_size
                )
                
                start_time = time.time()
                chunk_start_time = start_time
                chunk_downloaded = 0
                
                for chunk in response.iter_content(chunk_size=task.chunk_size):
                    if not self._running or task.status == "paused":
                        break
                        
                    if chunk:
                        # 写入数据
                        f.write(chunk)
                        f.flush()
                        
                        # 更新下载进度
                        chunk_size = len(chunk)
                        task.downloaded_size += chunk_size
                        chunk_downloaded += chunk_size
                        
                        # 计算速度和剩余时间
                        now = time.time()
                        elapsed = now - chunk_start_time
                        if elapsed >= 1:
                            task.current_speed = int(chunk_downloaded / elapsed)
                            if task.total_size > 0:
                                remaining_bytes = task.total_size - task.downloaded_size
                                task.remaining_time = timedelta(
                                    seconds=int(remaining_bytes / task.current_speed)
                                )
                            chunk_start_time = now
                            chunk_downloaded = 0
                            
                        # 速度限制
                        if task.speed_limit:
                            required_time = chunk_size / task.speed_limit
                            actual_time = time.time() - start_time
                            if actual_time < required_time:
                                time.sleep(required_time - actual_time)
                                
                        # 回调进度
                        if task.progress_callback:
                            task.progress_callback({
                                'task_id': task.id,
                                'total_size': task.total_size,
                                'downloaded_size': task.downloaded_size,
                                'progress': (
                                    task.downloaded_size / task.total_size
                                    if task.total_size > 0 else 0
                                ),
                                'current_speed': task.current_speed,
                                'average_speed': task.average_speed,
                                'remaining_time': task.remaining_time
                            })
                            
            # 完成下载
            task.status = "completed"
            task.finished_at = datetime.now()
            self._completed_tasks[task.id] = task
            self.stats['completed_tasks'] += 1
            
        except Exception as e:
            # 处理错误
            task.status = "failed"
            task.error = str(e)
            self._failed_tasks[task.id] = task
            self.stats['failed_tasks'] += 1
            logger.error(f"下载失败: {e}")
            
        finally:
            # 清理任务
            if task.id in self._active_tasks:
                del self._active_tasks[task.id]
            self.stats['active_tasks'] = len(self._active_tasks)
            
    def _make_request(
        self,
        url: str,
        method: str = "GET",
        **kwargs
    ) -> Any:
        """发送HTTP请求。
        
        Args:
            url: 请求URL
            method: 请求方法
            **kwargs: 其他参数
            
        Returns:
            Any: 响应对象
            
        Raises:
            NetworkError: 网络错误
            AuthError: 认证错误
        """
        import requests
        
        # 添加签名
        if self._secret_key:
            timestamp = str(int(time.time()))
            signature = self._sign_request(url, timestamp)
            kwargs.setdefault('headers', {}).update({
                'X-Timestamp': timestamp,
                'X-Signature': signature
            })
            
        # 检查缓存
        if self.cache and method == "GET":
            cached = self.cache.get(url)
            if cached:
                return cached
                
        try:
            # 发送请求
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            
            # 缓存响应
            if self.cache and method == "GET":
                self.cache.set(url, response)
                
            return response
            
        except requests.exceptions.RequestException as e:
            if isinstance(e, requests.exceptions.HTTPError):
                if e.response.status_code == 401:
                    raise AuthError("认证失败")
                elif e.response.status_code == 403:
                    raise AuthError("无权访问")
            raise NetworkError(f"网络请求失败: {e}")
            
    def _sign_request(self, url: str, timestamp: str) -> str:
        """签名请求。
        
        Args:
            url: 请求URL
            timestamp: 时间戳
            
        Returns:
            str: 签名
        """
        if not self._secret_key:
            return ""
            
        message = f"{url}{timestamp}".encode()
        signature = hmac.new(
            self._secret_key,
            message,
            hashlib.sha256
        ).hexdigest()
        
        return signature
        
    def add_task(
        self,
        url: str,
        save_path: Path,
        **kwargs
    ) -> str:
        """添加下载任务。
        
        Args:
            url: 下载URL
            save_path: 保存路径
            **kwargs: 其他参数
            
        Returns:
            str: 任务ID
        """
        # 生成任务ID
        task_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()
        
        # 创建任务
        task = DownloadTask(
            id=task_id,
            url=url,
            save_path=save_path,
            **kwargs
        )
        
        # 添加到队列
        self._task_queue.put((task.priority, task))
        self.stats['total_tasks'] += 1
        
        return task_id
        
    def pause_task(self, task_id: str):
        """暂停任务。
        
        Args:
            task_id: 任务ID
        """
        if task_id in self._active_tasks:
            self._active_tasks[task_id].status = "paused"
            
    def resume_task(self, task_id: str):
        """恢复任务。
        
        Args:
            task_id: 任务ID
        """
        if task_id in self._active_tasks:
            self._active_tasks[task_id].status = "downloading"
            
    def cancel_task(self, task_id: str):
        """取消任务。
        
        Args:
            task_id: 任务ID
        """
        if task_id in self._active_tasks:
            self._active_tasks[task_id].status = "cancelled"
            
    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务。
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[DownloadTask]: 下载任务
        """
        return (
            self._active_tasks.get(task_id) or
            self._completed_tasks.get(task_id) or
            self._failed_tasks.get(task_id)
        )
        
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息。
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return self.stats.copy()
        
    def pause_all(self):
        """暂停所有任务。"""
        self._paused = True
        for task in self._active_tasks.values():
            task.status = "paused"
            
    def resume_all(self):
        """恢复所有任务。"""
        self._paused = False
        for task in self._active_tasks.values():
            if task.status == "paused":
                task.status = "downloading"
                
    def stop(self):
        """停止调度器。"""
        self._running = False
        self._thread_pool.shutdown(wait=True) 