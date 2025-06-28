"""告警管理器模块。

负责加载告警规则并处理告警事件。
支持多种告警动作和通知方式。
"""

import os
import yaml
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum, auto

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """告警级别。"""
    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()

@dataclass
class AlertRule:
    """告警规则。"""
    name: str
    metric: str
    threshold: float
    duration: int
    action: str
    message: str
    severity: AlertSeverity
    
@dataclass
class AlertEvent:
    """告警事件。"""
    rule: AlertRule
    value: float
    timestamp: datetime
    message: str

class AlertManager:
    """告警管理器。
    
    负责加载和处理告警规则。
    
    Attributes:
        rules_file: str, 规则配置文件路径
        _rules: List[AlertRule], 告警规则列表
        _alert_history: Dict[str, List[AlertEvent]], 告警历史
        _last_alert: Dict[str, datetime], 最后告警时间
    """
    
    def __init__(self, rules_file: str):
        """初始化告警管理器。
        
        Args:
            rules_file: 规则配置文件路径
        """
        self.rules_file = rules_file
        self._rules: List[AlertRule] = []
        self._alert_history: Dict[str, List[AlertEvent]] = {}
        self._last_alert: Dict[str, datetime] = {}
        self._lock = threading.Lock()
        
        # 加载规则
        self.load_rules()
        
        logger.info(f"告警管理器初始化完成，已加载 {len(self._rules)} 条规则")
        
    def load_rules(self) -> None:
        """加载告警规则。"""
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            # 清空现有规则
            self._rules.clear()
            
            # 解析规则
            for rule in config.get('rules', []):
                self._rules.append(AlertRule(
                    name=rule['name'],
                    metric=rule['metric'],
                    threshold=float(rule['threshold']),
                    duration=int(rule['duration']),
                    action=rule['action'],
                    message=rule['message'],
                    severity=AlertSeverity[rule['severity'].upper()]
                ))
                
            logger.info(f"成功加载 {len(self._rules)} 条告警规则")
            
        except Exception as e:
            logger.error(f"加载告警规则失败: {str(e)}")
            
    def check_alerts(self, stats: Dict[str, Any]) -> List[AlertEvent]:
        """检查告警规则。
        
        Args:
            stats: 资源统计信息
            
        Returns:
            List[AlertEvent]: 触发的告警事件列表
        """
        triggered_alerts = []
        
        with self._lock:
            for rule in self._rules:
                # 获取指标值
                value = stats.get(rule.metric)
                if value is None:
                    continue
                    
                # 检查是否超过阈值
                if float(value) > rule.threshold:
                    # 检查告警间隔
                    last_alert = self._last_alert.get(rule.name)
                    if last_alert:
                        if datetime.now() - last_alert < timedelta(seconds=rule.duration):
                            continue
                            
                    # 创建告警事件
                    event = AlertEvent(
                        rule=rule,
                        value=float(value),
                        timestamp=datetime.now(),
                        message=rule.message.format(value=value)
                    )
                    
                    # 更新最后告警时间
                    self._last_alert[rule.name] = event.timestamp
                    
                    # 添加到历史记录
                    if rule.name not in self._alert_history:
                        self._alert_history[rule.name] = []
                    self._alert_history[rule.name].append(event)
                    
                    # 添加到触发列表
                    triggered_alerts.append(event)
                    
                    # 记录告警日志
                    logger.warning(
                        f"触发告警: {rule.name} "
                        f"({rule.metric}={value}, "
                        f"阈值={rule.threshold})"
                    )
                    
        return triggered_alerts
        
    def handle_alert(self, event: AlertEvent) -> None:
        """处理告警事件。
        
        Args:
            event: 告警事件
        """
        try:
            # 根据动作类型处理
            if event.rule.action == 'notify':
                self._handle_notification(event)
            elif event.rule.action == 'restart_worker':
                self._handle_restart(event)
            elif event.rule.action == 'throttle':
                self._handle_throttle(event)
            else:
                logger.warning(f"未知的告警动作: {event.rule.action}")
                
        except Exception as e:
            logger.error(f"处理告警事件失败: {str(e)}")
            
    def _handle_notification(self, event: AlertEvent) -> None:
        """处理通知类告警。"""
        # TODO: 实现通知逻辑（邮件、短信等）
        logger.info(f"发送告警通知: {event.message}")
        
    def _handle_restart(self, event: AlertEvent) -> None:
        """处理重启类告警。"""
        # TODO: 实现重启逻辑
        logger.info(f"执行重启操作: {event.message}")
        
    def _handle_throttle(self, event: AlertEvent) -> None:
        """处理限流类告警。"""
        # TODO: 实现限流逻辑
        logger.info(f"执行限流操作: {event.message}")
        
    def get_alert_history(
        self,
        rule_name: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[AlertEvent]:
        """获取告警历史。
        
        Args:
            rule_name: 规则名称
            severity: 告警级别
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            List[AlertEvent]: 告警事件列表
        """
        with self._lock:
            # 获取所有告警
            all_alerts = []
            for alerts in self._alert_history.values():
                all_alerts.extend(alerts)
                
            # 按规则名称过滤
            if rule_name:
                all_alerts = [
                    alert for alert in all_alerts
                    if alert.rule.name == rule_name
                ]
                
            # 按级别过滤
            if severity:
                all_alerts = [
                    alert for alert in all_alerts
                    if alert.rule.severity == severity
                ]
                
            # 按时间过滤
            if start_time:
                all_alerts = [
                    alert for alert in all_alerts
                    if alert.timestamp >= start_time
                ]
            if end_time:
                all_alerts = [
                    alert for alert in all_alerts
                    if alert.timestamp <= end_time
                ]
                
            # 按时间排序
            all_alerts.sort(key=lambda x: x.timestamp)
            
            return all_alerts 