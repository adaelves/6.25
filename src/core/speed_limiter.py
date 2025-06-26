"""下载速度限制器模块。

提供基于令牌桶算法的下载速度限制功能。
"""

import time
import asyncio
from typing import List, Tuple
from collections import deque

class SpeedLimiter:
    """下载速度限制器。
    
    使用令牌桶算法限制下载速度。
    支持同步和异步操作。
    
    Attributes:
        speed_limit: int, 速度限制(bytes/s)
        token_bucket: float, 令牌桶当前容量
        last_update: float, 上次更新时间
        window_size: float, 统计窗口大小(秒)
        bytes_transferred: deque, 传输字节统计队列
    """
    
    def __init__(self, speed_limit: int, window_size: float = 1.0):
        """初始化速度限制器。
        
        Args:
            speed_limit: 速度限制(bytes/s)
            window_size: 统计窗口大小(秒)
        """
        self.speed_limit = speed_limit
        self.token_bucket = speed_limit
        self.last_update = time.monotonic()
        self.window_size = window_size
        self.bytes_transferred = deque()
        
    def _update_bucket(self) -> None:
        """更新令牌桶。"""
        now = time.monotonic()
        time_passed = now - self.last_update
        
        # 更新令牌桶
        self.token_bucket = min(
            self.speed_limit,
            self.token_bucket + time_passed * self.speed_limit
        )
        self.last_update = now
        
    def _clean_stats(self) -> None:
        """清理过期的统计数据。"""
        now = time.monotonic()
        while (self.bytes_transferred and
               self.bytes_transferred[0][0] < now - self.window_size):
            self.bytes_transferred.popleft()
            
    def _record_transfer(self, size: int) -> None:
        """记录传输字节数。
        
        Args:
            size: 传输的字节数
        """
        now = time.monotonic()
        self.bytes_transferred.append((now, size))
        self._clean_stats()
        
    async def wait(self, size: int) -> None:
        """异步等待令牌。
        
        Args:
            size: 需要的令牌数(字节数)
        """
        while True:
            self._update_bucket()
            
            if size <= self.token_bucket:
                self.token_bucket -= size
                self._record_transfer(size)
                break
                
            # 计算需要等待的时间
            wait_time = (size - self.token_bucket) / self.speed_limit
            await asyncio.sleep(wait_time)
            
    def wait_sync(self, size: int) -> None:
        """同步等待令牌。
        
        Args:
            size: 需要的令牌数(字节数)
        """
        while True:
            self._update_bucket()
            
            if size <= self.token_bucket:
                self.token_bucket -= size
                self._record_transfer(size)
                break
                
            # 计算需要等待的时间
            wait_time = (size - self.token_bucket) / self.speed_limit
            time.sleep(wait_time)
            
    @property
    def current_speed(self) -> float:
        """当前速度(bytes/s)。"""
        self._clean_stats()
        
        if not self.bytes_transferred:
            return 0.0
            
        total_bytes = sum(size for _, size in self.bytes_transferred)
        window = min(
            self.window_size,
            time.monotonic() - self.bytes_transferred[0][0]
        ) or self.window_size
        
        return total_bytes / window
        
    def reset(self) -> None:
        """重置速度限制器。"""
        self.token_bucket = self.speed_limit
        self.last_update = time.monotonic()
        self.bytes_transferred.clear() 