"""性能监控系统。"""

import time
import psutil
import logging
import threading
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from enum import Enum, auto

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """指标类型。"""
    COUNTER = auto()  # 计数器类型
    GAUGE = auto()    # 瞬时值类型
    RATE = auto()     # 速率类型

@dataclass
class Metric:
    """监控指标。"""
    name: str
    type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)

class AlertLevel(Enum):
    """告警级别。"""
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

@dataclass
class Alert:
    """告警信息。"""
    level: AlertLevel
    message: str
    metric: Metric
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    
class BandwidthCounter:
    """带宽统计器。"""
    
    def __init__(self, window_size: int = 60):
        """初始化带宽统计器。
        
        Args:
            window_size: 统计窗口大小（秒）
        """
        self.window_size = window_size
        self.bytes_in = deque(maxlen=window_size)
        self.bytes_out = deque(maxlen=window_size)
        self.last_check = time.time()
        
        # 获取初始网络计数器
        net_io = psutil.net_io_counters()
        self.last_bytes_in = net_io.bytes_recv
        self.last_bytes_out = net_io.bytes_sent
        
    def update(self) -> Dict[str, float]:
        """更新带宽统计。
        
        Returns:
            Dict[str, float]: 当前带宽数据
            {
                'in_speed': 入站速度（MB/s）,
                'out_speed': 出站速度（MB/s）,
                'in_total': 入站总量（MB）,
                'out_total': 出站总量（MB）
            }
        """
        now = time.time()
        interval = now - self.last_check
        
        # 获取当前网络计数器
        net_io = psutil.net_io_counters()
        
        # 计算速度
        bytes_in = net_io.bytes_recv - self.last_bytes_in
        bytes_out = net_io.bytes_sent - self.last_bytes_out
        
        in_speed = bytes_in / interval / 1024 / 1024  # MB/s
        out_speed = bytes_out / interval / 1024 / 1024  # MB/s
        
        # 更新历史数据
        self.bytes_in.append(in_speed)
        self.bytes_out.append(out_speed)
        
        # 更新基准值
        self.last_check = now
        self.last_bytes_in = net_io.bytes_recv
        self.last_bytes_out = net_io.bytes_sent
        
        return {
            'in_speed': in_speed,
            'out_speed': out_speed,
            'in_total': net_io.bytes_recv / 1024 / 1024,  # MB
            'out_total': net_io.bytes_sent / 1024 / 1024  # MB
        }
        
class ErrorTracker:
    """错误跟踪器。"""
    
    def __init__(self, window_size: int = 3600):
        """初始化错误跟踪器。
        
        Args:
            window_size: 统计窗口大小（秒）
        """
        self.window_size = window_size
        self.errors = deque(maxlen=window_size)
        self.total_requests = deque(maxlen=window_size)
        
    def record_error(self, error: Exception, context: Dict[str, Any] = None):
        """记录错误。
        
        Args:
            error: 异常对象
            context: 错误上下文
        """
        now = datetime.now()
        self.errors.append({
            'time': now,
            'error': error,
            'context': context or {}
        })
        
    def record_request(self):
        """记录请求。"""
        self.total_requests.append(datetime.now())
        
    def get_error_rate(self, duration: int = 60) -> float:
        """获取错误率。
        
        Args:
            duration: 统计时间范围（秒）
            
        Returns:
            float: 错误率（0-1）
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=duration)
        
        # 统计时间范围内的错误和请求数
        recent_errors = sum(1 for e in self.errors if e['time'] > cutoff)
        recent_requests = sum(1 for r in self.total_requests if r > cutoff)
        
        if recent_requests == 0:
            return 0.0
            
        return recent_errors / recent_requests
        
    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误统计摘要。"""
        error_types = {}
        for error in self.errors:
            error_type = type(error['error']).__name__
            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += 1
            
        return {
            'total_errors': len(self.errors),
            'error_types': error_types,
            'error_rate': self.get_error_rate()
        }

class ResourceMonitor:
    """资源监控器。"""
    
    def __init__(self, interval: int = 1):
        """初始化资源监控器。
        
        Args:
            interval: 采集间隔（秒）
        """
        self.interval = interval
        self.metrics: List[Metric] = []
        self._stop = threading.Event()
        self._thread = None
        
    def start(self):
        """启动监控。"""
        if self._thread is not None:
            return
            
        self._stop.clear()
        self._thread = threading.Thread(target=self._collect_metrics)
        self._thread.daemon = True
        self._thread.start()
        
    def stop(self):
        """停止监控。"""
        if self._thread is None:
            return
            
        self._stop.set()
        self._thread.join()
        self._thread = None
        
    def _collect_metrics(self):
        """收集系统指标。"""
        while not self._stop.is_set():
            try:
                # CPU使用率
                cpu_percent = psutil.cpu_percent(interval=None)
                self.metrics.append(Metric(
                    name='cpu_usage',
                    type=MetricType.GAUGE,
                    value=cpu_percent
                ))
                
                # 内存使用率
                memory = psutil.virtual_memory()
                self.metrics.append(Metric(
                    name='memory_usage',
                    type=MetricType.GAUGE,
                    value=memory.percent
                ))
                
                # 磁盘使用率
                disk = psutil.disk_usage('/')
                self.metrics.append(Metric(
                    name='disk_usage',
                    type=MetricType.GAUGE,
                    value=disk.percent
                ))
                
                # 系统负载
                load = psutil.getloadavg()
                self.metrics.append(Metric(
                    name='system_load',
                    type=MetricType.GAUGE,
                    value=load[0]  # 1分钟负载
                ))
                
            except Exception as e:
                logger.error(f"采集系统指标失败: {e}")
                
            self._stop.wait(self.interval)
            
    def get_metrics(self) -> List[Metric]:
        """获取收集的指标。"""
        return self.metrics.copy()

class AlertManager:
    """告警管理器。"""
    
    def __init__(self):
        """初始化告警管理器。"""
        self.alerts: List[Alert] = []
        self.handlers: Dict[AlertLevel, List[Callable]] = {
            level: [] for level in AlertLevel
        }
        
    def add_handler(self, level: AlertLevel, handler: Callable):
        """添加告警处理器。
        
        Args:
            level: 告警级别
            handler: 处理函数
        """
        self.handlers[level].append(handler)
        
    def trigger_alert(self, alert: Alert):
        """触发告警。
        
        Args:
            alert: 告警信息
        """
        self.alerts.append(alert)
        
        # 调用对应级别的处理器
        for handler in self.handlers[alert.level]:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"处理告警失败: {e}")
                
    def resolve_alert(self, alert: Alert):
        """解决告警。
        
        Args:
            alert: 告警信息
        """
        alert.resolved = True
        logger.info(f"告警已解决: {alert.message}")
        
    def get_active_alerts(self) -> List[Alert]:
        """获取未解决的告警。"""
        return [a for a in self.alerts if not a.resolved]

class PerformanceMonitor:
    """性能监控系统。"""
    
    def __init__(
        self,
        check_interval: int = 60,
        alert_interval: int = 300
    ):
        """初始化监控系统。
        
        Args:
            check_interval: 检查间隔（秒）
            alert_interval: 告警间隔（秒）
        """
        # 监控组件
        self.bandwidth = BandwidthCounter()
        self.error_tracker = ErrorTracker()
        self.resource_monitor = ResourceMonitor()
        self.alert_manager = AlertManager()
        
        # 配置参数
        self.check_interval = check_interval
        self.alert_interval = alert_interval
        self._last_alert = {}
        
        # 控制标志
        self._stop = threading.Event()
        self._thread = None
        
    def start(self):
        """启动监控。"""
        if self._thread is not None:
            return
            
        # 启动资源监控
        self.resource_monitor.start()
        
        # 启动检查线程
        self._stop.clear()
        self._thread = threading.Thread(target=self._check_loop)
        self._thread.daemon = True
        self._thread.start()
        
        logger.info("性能监控系统已启动")
        
    def stop(self):
        """停止监控。"""
        if self._thread is None:
            return
            
        self._stop.set()
        self._thread.join()
        self._thread = None
        
        # 停止资源监控
        self.resource_monitor.stop()
        
        logger.info("性能监控系统已停止")
        
    def alert_rules(self) -> Dict[str, Callable[[], bool]]:
        """获取告警规则。
        
        Returns:
            Dict[str, Callable[[], bool]]: 规则字典
            {
                规则名称: 判断函数
            }
        """
        return {
            # CPU使用率超过90%
            'high_cpu': lambda: psutil.cpu_percent() > 90,
            
            # 内存使用率超过95%
            'oom_risk': lambda: psutil.virtual_memory().percent > 95,
            
            # 磁盘使用率超过90%
            'disk_full': lambda: psutil.disk_usage('/').percent > 90,
            
            # 系统负载过高
            'high_load': lambda: psutil.getloadavg()[0] > psutil.cpu_count() * 2,
            
            # 错误率超过10%
            'high_error_rate': lambda: self.error_tracker.get_error_rate() > 0.1,
            
            # 带宽使用率过高
            'high_bandwidth': lambda: (
                self.bandwidth.update()['in_speed'] > 100 or  # 100MB/s
                self.bandwidth.update()['out_speed'] > 100
            )
        }
        
    def _check_loop(self):
        """检查循环。"""
        while not self._stop.is_set():
            try:
                self._check_alerts()
            except Exception as e:
                logger.error(f"检查告警失败: {e}")
                
            self._stop.wait(self.check_interval)
            
    def _check_alerts(self):
        """检查告警规则。"""
        now = datetime.now()
        rules = self.alert_rules()
        
        for name, check in rules.items():
            # 检查告警间隔
            if (name in self._last_alert and
                now - self._last_alert[name] < timedelta(seconds=self.alert_interval)):
                continue
                
            try:
                if check():
                    # 创建指标
                    metric = None
                    if name == 'high_cpu':
                        metric = Metric('cpu_usage', MetricType.GAUGE, psutil.cpu_percent())
                    elif name == 'oom_risk':
                        metric = Metric('memory_usage', MetricType.GAUGE, psutil.virtual_memory().percent)
                    elif name == 'disk_full':
                        metric = Metric('disk_usage', MetricType.GAUGE, psutil.disk_usage('/').percent)
                    elif name == 'high_load':
                        metric = Metric('system_load', MetricType.GAUGE, psutil.getloadavg()[0])
                    elif name == 'high_error_rate':
                        metric = Metric('error_rate', MetricType.RATE, self.error_tracker.get_error_rate())
                    elif name == 'high_bandwidth':
                        bandwidth = self.bandwidth.update()
                        metric = Metric('bandwidth_usage', MetricType.GAUGE, max(
                            bandwidth['in_speed'],
                            bandwidth['out_speed']
                        ))
                        
                    # 触发告警
                    alert = Alert(
                        level=AlertLevel.WARNING,
                        message=f"检测到{name}告警",
                        metric=metric
                    )
                    self.alert_manager.trigger_alert(alert)
                    
                    # 更新告警时间
                    self._last_alert[name] = now
                    
            except Exception as e:
                logger.error(f"检查规则[{name}]失败: {e}")
                
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态摘要。"""
        return {
            'cpu_usage': psutil.cpu_percent(),
            'memory_usage': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'system_load': psutil.getloadavg()[0],
            'error_rate': self.error_tracker.get_error_rate(),
            'bandwidth': self.bandwidth.update(),
            'active_alerts': len(self.alert_manager.get_active_alerts())
        } 