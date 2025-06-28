"""监控系统测试模块。

测试资源监控和告警功能。
"""

import unittest
import tempfile
import os
import time
import yaml
from datetime import datetime, timedelta
from src.monitoring.resource_monitor import ResourceMonitor
from src.monitoring.alert_manager import AlertManager, AlertSeverity

class TestMonitoring(unittest.TestCase):
    """监控系统测试类。"""
    
    def setUp(self):
        """测试初始化。"""
        # 创建临时规则文件
        self.rules_file = self._create_test_rules()
        
        # 初始化监控器
        self.resource_monitor = ResourceMonitor(
            update_interval=0.1,  # 快速更新以便测试
            history_size=10
        )
        
        # 初始化告警管理器
        self.alert_manager = AlertManager(self.rules_file)
        
    def _create_test_rules(self):
        """创建测试规则文件。"""
        rules = {
            'global': {
                'update_interval': 0.1,
                'history_size': 10,
                'alert_interval': 1
            },
            'rules': [
                {
                    'name': 'test_cpu',
                    'metric': 'cpu_percent',
                    'threshold': 50,
                    'duration': 1,
                    'action': 'notify',
                    'message': 'CPU使用率超过50%: {value}%',
                    'severity': 'warning'
                },
                {
                    'name': 'test_memory',
                    'metric': 'memory_percent',
                    'threshold': 80,
                    'duration': 1,
                    'action': 'restart_worker',
                    'message': '内存使用率超过80%: {value}%',
                    'severity': 'critical'
                }
            ]
        }
        
        # 创建临时文件
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            yaml.dump(rules, f)
            
        return path
        
    def test_resource_monitor(self):
        """测试资源监控器。"""
        # 启动监控
        self.resource_monitor.start()
        
        # 等待收集数据
        time.sleep(0.5)
        
        # 获取当前统计信息
        stats = self.resource_monitor.get_current_stats()
        
        # 验证统计信息
        self.assertIn('cpu_percent', stats)
        self.assertIn('memory_percent', stats)
        self.assertIn('disk_percent', stats)
        self.assertIn('timestamp', stats)
        
        # 验证数值范围
        self.assertGreaterEqual(stats['cpu_percent'], 0)
        self.assertLessEqual(stats['cpu_percent'], 100)
        self.assertGreaterEqual(stats['memory_percent'], 0)
        self.assertLessEqual(stats['memory_percent'], 100)
        
        # 停止监控
        self.resource_monitor.stop()
        
    def test_alert_manager(self):
        """测试告警管理器。"""
        # 验证规则加载
        self.assertEqual(len(self.alert_manager._rules), 2)
        
        # 模拟资源统计数据
        mock_stats = {
            'cpu_percent': 60,
            'memory_percent': 85,
            'disk_percent': 70,
            'timestamp': datetime.now().isoformat()
        }
        
        # 检查告警触发
        alerts = self.alert_manager.check_alerts(mock_stats)
        self.assertEqual(len(alerts), 2)  # 应该触发两个告警
        
        # 验证CPU告警
        cpu_alert = next(a for a in alerts if a.rule.name == 'test_cpu')
        self.assertEqual(cpu_alert.rule.severity, AlertSeverity.WARNING)
        self.assertEqual(cpu_alert.value, 60)
        
        # 验证内存告警
        mem_alert = next(a for a in alerts if a.rule.name == 'test_memory')
        self.assertEqual(mem_alert.rule.severity, AlertSeverity.CRITICAL)
        self.assertEqual(mem_alert.value, 85)
        
        # 测试告警间隔
        alerts = self.alert_manager.check_alerts(mock_stats)
        self.assertEqual(len(alerts), 0)  # 应该不触发新告警
        
        # 等待告警间隔
        time.sleep(1.1)
        
        # 再次检查告警
        alerts = self.alert_manager.check_alerts(mock_stats)
        self.assertEqual(len(alerts), 2)  # 应该再次触发告警
        
    def test_alert_history(self):
        """测试告警历史。"""
        # 模拟多次告警
        mock_stats = {
            'cpu_percent': 60,
            'memory_percent': 85,
            'timestamp': datetime.now().isoformat()
        }
        
        # 触发第一次告警
        self.alert_manager.check_alerts(mock_stats)
        time.sleep(1.1)
        
        # 触发第二次告警
        self.alert_manager.check_alerts(mock_stats)
        time.sleep(1.1)
        
        # 获取所有告警历史
        all_history = self.alert_manager.get_alert_history()
        self.assertEqual(len(all_history), 4)  # 应该有4个告警事件
        
        # 按规则名称过滤
        cpu_history = self.alert_manager.get_alert_history(rule_name='test_cpu')
        self.assertEqual(len(cpu_history), 2)
        
        # 按告警级别过滤
        critical_history = self.alert_manager.get_alert_history(
            severity=AlertSeverity.CRITICAL
        )
        self.assertEqual(len(critical_history), 2)
        
        # 按时间范围过滤
        recent_history = self.alert_manager.get_alert_history(
            start_time=datetime.now() - timedelta(seconds=2)
        )
        self.assertEqual(len(recent_history), 2)
        
    def test_integrated_monitoring(self):
        """测试监控系统集成。"""
        # 启动资源监控
        self.resource_monitor.start()
        
        # 等待收集数据
        time.sleep(0.5)
        
        # 获取监控数据并检查告警
        stats = self.resource_monitor.get_current_stats()
        alerts = self.alert_manager.check_alerts(stats)
        
        # 处理告警
        for alert in alerts:
            self.alert_manager.handle_alert(alert)
            
        # 验证告警历史
        history = self.alert_manager.get_alert_history()
        self.assertEqual(len(history), len(alerts))
        
        # 停止监控
        self.resource_monitor.stop()
        
    def tearDown(self):
        """测试清理。"""
        # 停止监控
        self.resource_monitor.stop()
        
        # 删除临时文件
        if os.path.exists(self.rules_file):
            os.remove(self.rules_file)
            
if __name__ == '__main__':
    unittest.main() 