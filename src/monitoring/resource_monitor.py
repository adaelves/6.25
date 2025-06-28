"""资源监控模块。

负责监控系统资源使用情况，包括：
- CPU使用率
- 内存使用率
- 磁盘使用情况
- 网络连接状态
- 下载任务数量
"""

import os
import time
import logging
import threading
from typing import Dict, Any, Optional, List
import psutil
from datetime import datetime

logger = logging.getLogger(__name__)

class ResourceMonitor:
    """系统资源监控器。
    
    监控系统资源使用情况，并提供告警机制。
    
    Attributes:
        update_interval: float, 更新间隔（秒）
        history_size: int, 历史记录大小
        _stats_history: List[Dict], 资源统计历史记录
        _monitor_thread: Optional[threading.Thread], 监控线程
        _stop_flag: threading.Event, 停止标志
    """
    
    def __init__(
        self,
        update_interval: float = 1.0,
        history_size: int = 3600
    ):
        """初始化资源监控器。
        
        Args:
            update_interval: 更新间隔（秒）
            history_size: 历史记录大小（条数）
        """
        self.update_interval = update_interval
        self.history_size = history_size
        
        # 初始化历史记录
        self._stats_history: List[Dict] = []
        
        # 监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        
        # 初始化进程
        self._process = psutil.Process()
        
        logger.info(
            f"资源监控器初始化完成 "
            f"(间隔={update_interval}秒, "
            f"历史={history_size}条)"
        )
        
    def start(self) -> None:
        """启动资源监控。"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("监控器已在运行")
            return
            
        self._stop_flag.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="ResourceMonitor"
        )
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        
        logger.info("资源监控器已启动")
        
    def stop(self) -> None:
        """停止资源监控。"""
        if not self._monitor_thread:
            return
            
        self._stop_flag.set()
        self._monitor_thread.join()
        self._monitor_thread = None
        
        logger.info("资源监控器已停止")
        
    def get_current_stats(self) -> Dict[str, Any]:
        """获取当前资源统计信息。
        
        Returns:
            Dict[str, Any]: 资源统计信息
        """
        try:
            # CPU信息
            cpu_stats = {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'cpu_count': psutil.cpu_count(),
                'cpu_freq': psutil.cpu_freq().current if psutil.cpu_freq() else None
            }
            
            # 内存信息
            mem = psutil.virtual_memory()
            mem_stats = {
                'memory_total': mem.total,
                'memory_available': mem.available,
                'memory_percent': mem.percent,
                'memory_used': mem.used
            }
            
            # 磁盘信息
            disk = psutil.disk_usage('/')
            disk_stats = {
                'disk_total': disk.total,
                'disk_free': disk.free,
                'disk_percent': disk.percent
            }
            
            # 网络信息
            net = psutil.net_io_counters()
            net_stats = {
                'net_bytes_sent': net.bytes_sent,
                'net_bytes_recv': net.bytes_recv,
                'net_packets_sent': net.packets_sent,
                'net_packets_recv': net.packets_recv
            }
            
            # 进程信息
            proc_stats = {
                'open_files': len(self._process.open_files()),
                'connections': len(self._process.connections()),
                'threads': self._process.num_threads(),
                'memory_percent': self._process.memory_percent()
            }
            
            # 合并所有统计信息
            stats = {
                'timestamp': datetime.now().isoformat(),
                **cpu_stats,
                **mem_stats,
                **disk_stats,
                **net_stats,
                **proc_stats
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取资源统计信息失败: {str(e)}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
            
    def get_stats_history(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """获取历史统计信息。
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            List[Dict[str, Any]]: 历史统计信息列表
        """
        if not self._stats_history:
            return []
            
        if not start_time and not end_time:
            return self._stats_history
            
        filtered_stats = []
        for stats in self._stats_history:
            timestamp = datetime.fromisoformat(stats['timestamp'])
            if start_time and timestamp < start_time:
                continue
            if end_time and timestamp > end_time:
                continue
            filtered_stats.append(stats)
            
        return filtered_stats
        
    def _monitor_loop(self) -> None:
        """监控循环。"""
        while not self._stop_flag.is_set():
            try:
                # 获取当前统计信息
                stats = self.get_current_stats()
                
                # 添加到历史记录
                self._stats_history.append(stats)
                
                # 限制历史记录大小
                if len(self._stats_history) > self.history_size:
                    self._stats_history = self._stats_history[-self.history_size:]
                    
                # 检查资源告警
                self._check_alerts(stats)
                
            except Exception as e:
                logger.error(f"监控循环异常: {str(e)}")
                
            # 等待下次更新
            self._stop_flag.wait(self.update_interval)
            
    def _check_alerts(self, stats: Dict[str, Any]) -> None:
        """检查资源告警。
        
        Args:
            stats: 当前统计信息
        """
        # CPU使用率告警
        if stats.get('cpu_percent', 0) > 90:
            logger.warning(f"CPU使用率过高: {stats['cpu_percent']}%")
            
        # 内存使用率告警
        if stats.get('memory_percent', 0) > 90:
            logger.warning(f"内存使用率过高: {stats['memory_percent']}%")
            
        # 磁盘使用率告警
        if stats.get('disk_percent', 0) > 90:
            logger.warning(f"磁盘使用率过高: {stats['disk_percent']}%")
            
        # 进程内存使用告警
        if stats.get('memory_percent', 0) > 90:
            logger.warning(f"进程内存使用率过高: {stats['memory_percent']}%") 