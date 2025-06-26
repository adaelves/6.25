"""速率限制服务。

提供各平台API请求的速率限制功能。
支持Twitter、B站等平台的自定义限制规则。
"""

import time
import logging
from typing import Dict, Tuple, List, Optional
from threading import Lock
from collections import deque

logger = logging.getLogger(__name__)

class PlatformRateLimiter:
    """平台速率限制器。
    
    基于滑动窗口算法实现请求速率限制。
    支持多平台不同限制规则。
    线程安全。
    
    Attributes:
        RULES: Dict[str, Tuple[int, int]], 平台限制规则
            key: 平台名称
            value: (最大请求数, 时间窗口(秒))
    """
    
    # 平台限制规则
    RULES = {
        "twitter": (100, 900),   # 100次/15分钟
        "bilibili": (5, 1),      # 5次/秒
        "youtube": (10000, 86400)  # 10000次/天
    }
    
    def __init__(self):
        """初始化速率限制器。"""
        # 请求记录: {platform: deque[(timestamp, count)]}
        self._requests: Dict[str, deque] = {}
        # 平台锁: {platform: Lock}
        self._locks: Dict[str, Lock] = {}
        
    def _get_platform_lock(self, platform: str) -> Lock:
        """获取平台锁。
        
        Args:
            platform: 平台名称
            
        Returns:
            Lock: 平台对应的线程锁
        """
        if platform not in self._locks:
            self._locks[platform] = Lock()
        return self._locks[platform]
        
    def _init_platform(self, platform: str) -> None:
        """初始化平台记录。
        
        Args:
            platform: 平台名称
        """
        if platform not in self._requests:
            self._requests[platform] = deque()
            
    def _clean_old_requests(self, platform: str, window: int) -> None:
        """清理过期请求记录。
        
        Args:
            platform: 平台名称
            window: 时间窗口(秒)
        """
        now = time.time()
        while (self._requests[platform] and 
               now - self._requests[platform][0][0] > window):
            self._requests[platform].popleft()
            
    def check(self, platform: str) -> bool:
        """检查是否允许请求。
        
        Args:
            platform: 平台名称
            
        Returns:
            bool: 是否允许请求
            
        Raises:
            ValueError: 平台规则未定义
        """
        # 获取平台规则
        if platform not in self.RULES:
            raise ValueError(f"未定义平台 {platform} 的限制规则")
            
        max_requests, window = self.RULES[platform]
        
        # 获取平台锁
        with self._get_platform_lock(platform):
            # 初始化平台记录
            self._init_platform(platform)
            
            # 清理过期记录
            self._clean_old_requests(platform, window)
            
            # 计算当前请求数
            current_requests = sum(count for _, count in self._requests[platform])
            
            # 检查是否超限
            if current_requests >= max_requests:
                logger.warning(
                    f"平台 {platform} 请求超限: "
                    f"{current_requests}/{max_requests} 次/{window}秒"
                )
                return False
                
            # 记录新请求
            now = time.time()
            self._requests[platform].append((now, 1))
            
            logger.debug(
                f"平台 {platform} 当前请求: "
                f"{current_requests + 1}/{max_requests} 次/{window}秒"
            )
            return True
            
    def wait(self, platform: str) -> float:
        """计算需要等待的时间。
        
        Args:
            platform: 平台名称
            
        Returns:
            float: 需要等待的秒数
            
        Raises:
            ValueError: 平台规则未定义
        """
        # 获取平台规则
        if platform not in self.RULES:
            raise ValueError(f"未定义平台 {platform} 的限制规则")
            
        max_requests, window = self.RULES[platform]
        
        # 获取平台锁
        with self._get_platform_lock(platform):
            # 初始化平台记录
            self._init_platform(platform)
            
            # 清理过期记录
            self._clean_old_requests(platform, window)
            
            # 如果没有请求记录，无需等待
            if not self._requests[platform]:
                return 0
                
            # 计算最早请求的时间
            earliest_time = self._requests[platform][0][0]
            now = time.time()
            
            # 计算需要等待的时间
            wait_time = max(0, window - (now - earliest_time))
            
            return wait_time
            
    def reset(self, platform: Optional[str] = None) -> None:
        """重置请求记录。
        
        Args:
            platform: 平台名称，如果为None则重置所有平台
        """
        if platform:
            # 重置指定平台
            with self._get_platform_lock(platform):
                if platform in self._requests:
                    self._requests[platform].clear()
        else:
            # 重置所有平台
            for p in list(self._requests.keys()):
                self.reset(p)
                
# 创建全局实例
rate_limiter = PlatformRateLimiter()

def check_rate_limit(platform: str) -> bool:
    """便捷函数：检查是否允许请求。
    
    Args:
        platform: 平台名称
        
    Returns:
        bool: 是否允许请求
    """
    return rate_limiter.check(platform)

def wait_for_rate_limit(platform: str) -> float:
    """便捷函数：获取需要等待的时间。
    
    Args:
        platform: 平台名称
        
    Returns:
        float: 需要等待的秒数
    """
    return rate_limiter.wait(platform)

def reset_rate_limit(platform: Optional[str] = None) -> None:
    """便捷函数：重置速率限制。
    
    Args:
        platform: 平台名称，如果为None则重置所有平台
    """
    rate_limiter.reset(platform) 