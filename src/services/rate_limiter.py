"""速率限制服务模块。

提供通用的速率限制功能，支持：
- 基于时间窗口的限制
- 线程安全操作
- 异步等待
- 自定义错误处理
"""

import time
import asyncio
import logging
from threading import Lock
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RateLimitExceededError(Exception):
    """速率限制异常。"""
    
    def __init__(self, wait_time: float):
        """初始化异常。
        
        Args:
            wait_time: 需要等待的时间（秒）
        """
        self.wait_time = wait_time
        super().__init__(f"速率限制：需要等待 {wait_time:.2f} 秒")

class RateLimiter:
    """通用速率限制器。
    
    支持：
    - 基于固定时间窗口的限制
    - 线程安全操作
    - 同步/异步等待
    - 自定义错误处理
    
    Attributes:
        calls_per_minute: int, 每分钟允许的调用次数
        interval: float, 调用间隔（秒）
        last_call: float, 上次调用时间戳
        lock: Lock, 线程锁
        stats: Dict[str, Any], 统计信息
    """
    
    def __init__(
        self,
        calls_per_minute: int,
        error_on_exceed: bool = False
    ):
        """初始化速率限制器。
        
        Args:
            calls_per_minute: 每分钟允许的调用次数
            error_on_exceed: 是否在超出限制时抛出异常，默认等待
        """
        if calls_per_minute <= 0:
            raise ValueError("calls_per_minute 必须大于 0")
            
        self.calls_per_minute = calls_per_minute
        self.interval = 60.0 / calls_per_minute
        self.error_on_exceed = error_on_exceed
        
        self.last_call = 0.0
        self.lock = Lock()
        
        # 统计信息
        self.stats = {
            "total_calls": 0,
            "total_wait_time": 0.0,
            "max_wait_time": 0.0,
            "last_reset": time.time()
        }
        
    def wait(self) -> None:
        """等待直到可以进行下一次调用。
        
        如果 error_on_exceed 为 True，超出限制时抛出异常，
        否则会等待到下一个可用时间窗口。
        
        Raises:
            RateLimitExceededError: 超出速率限制且 error_on_exceed 为 True
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            wait_time = max(0, self.interval - elapsed)
            
            # 更新统计信息
            self.stats["total_calls"] += 1
            self.stats["total_wait_time"] += wait_time
            self.stats["max_wait_time"] = max(
                self.stats["max_wait_time"],
                wait_time
            )
            
            # 检查是否需要重置统计
            if now - self.stats["last_reset"] >= 3600:  # 每小时重置
                self._reset_stats(now)
            
            if wait_time > 0:
                if self.error_on_exceed:
                    raise RateLimitExceededError(wait_time)
                    
                logger.debug(f"速率限制：等待 {wait_time:.2f} 秒")
                time.sleep(wait_time)
                
            self.last_call = time.time()
            
    async def async_wait(self) -> None:
        """异步等待直到可以进行下一次调用。
        
        异步版本的 wait() 方法，用于协程环境。
        
        Raises:
            RateLimitExceededError: 超出速率限制且 error_on_exceed 为 True
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            wait_time = max(0, self.interval - elapsed)
            
            # 更新统计信息
            self.stats["total_calls"] += 1
            self.stats["total_wait_time"] += wait_time
            self.stats["max_wait_time"] = max(
                self.stats["max_wait_time"],
                wait_time
            )
            
            # 检查是否需要重置统计
            if now - self.stats["last_reset"] >= 3600:
                self._reset_stats(now)
            
            if wait_time > 0:
                if self.error_on_exceed:
                    raise RateLimitExceededError(wait_time)
                    
                logger.debug(f"速率限制：等待 {wait_time:.2f} 秒")
                await asyncio.sleep(wait_time)
                
            self.last_call = time.time()
            
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息。
        
        Returns:
            Dict[str, Any]: 包含以下统计信息：
            - total_calls: 总调用次数
            - total_wait_time: 总等待时间
            - max_wait_time: 最长等待时间
            - avg_wait_time: 平均等待时间
            - calls_per_minute: 每分钟调用次数限制
        """
        with self.lock:
            stats = self.stats.copy()
            stats["avg_wait_time"] = (
                stats["total_wait_time"] / stats["total_calls"]
                if stats["total_calls"] > 0
                else 0.0
            )
            stats["calls_per_minute"] = self.calls_per_minute
            return stats
            
    def _reset_stats(self, now: float) -> None:
        """重置统计信息。
        
        Args:
            now: 当前时间戳
        """
        self.stats.update({
            "total_calls": 0,
            "total_wait_time": 0.0,
            "max_wait_time": 0.0,
            "last_reset": now
        })
        
    def __enter__(self):
        """上下文管理器入口。"""
        self.wait()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        pass
        
    async def __aenter__(self):
        """异步上下文管理器入口。"""
        await self.async_wait()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口。"""
        pass 