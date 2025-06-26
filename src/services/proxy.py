"""代理服务模块。

提供代理服务器配置和管理功能。
"""

import logging
import yaml
import socket
import requests
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()

@dataclass
class ProxyConfig:
    """代理配置数据类。
    
    Attributes:
        address: str, 代理服务器地址
        type: str, 代理类型（http/socks5）
        timeout: int, 超时时间（秒）
        enabled: bool, 是否启用
    """
    address: str
    type: str
    timeout: int
    enabled: bool = True

class ProxyManager:
    """代理管理器。
    
    提供代理服务器的加载、测试和自动切换功能。
    
    Attributes:
        config_path: Path, 配置文件路径
        proxies: List[ProxyConfig], 代理配置列表
        current_index: int, 当前使用的代理索引
        retry_count: int, 当前代理重试次数
    """
    
    # 测试目标网站列表
    TEST_URLS = [
        "https://www.youtube.com/",
        "https://www.google.com/",
        "https://api.ipify.org?format=json"
    ]
    
    def __init__(self, config_path: Optional[Path] = None) -> None:
        """初始化代理管理器。
        
        Args:
            config_path: 可选的配置文件路径，默认为configs/proxies.yaml
        """
        if config_path is None:
            config_path = PROJECT_ROOT / "configs" / "proxies.yaml"
            
        self.config_path = config_path
        self.proxies: List[ProxyConfig] = []
        self.current_index = 0
        self.retry_count = 0
        self.max_retries = 3
        
        # 代理状态缓存，格式：{proxy_address: (is_available, last_check_time)}
        self._proxy_status_cache: Dict[str, Tuple[bool, float]] = {}
        # 缓存有效期（秒）
        self._cache_ttl = 300  # 5分钟
        
        # 确保配置目录存在
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 如果配置文件不存在，创建默认配置
        if not self.config_path.exists():
            self._create_default_config()
            
        self._load_config()
        logger.info(f"代理管理器初始化完成，配置文件路径：{self.config_path}")
        
    def _create_default_config(self) -> None:
        """创建默认的代理配置文件。"""
        default_config = {
            'proxies': [
                {
                    'address': '127.0.0.1:7890',
                    'type': 'http',
                    'timeout': 30,
                    'enabled': True
                }
            ]
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(default_config, f, allow_unicode=True)
            logger.info(f"已创建默认代理配置文件：{self.config_path}")
        except Exception as e:
            logger.error(f"创建默认配置文件失败: {e}")
            raise

    def _load_config(self) -> None:
        """从YAML文件加载代理配置。
        
        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML格式错误
        """
        try:
            if not self.config_path.exists():
                logger.warning(f"代理配置文件不存在: {self.config_path}")
                return
                
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            self.proxies = []
            for proxy in config.get('proxies', []):
                if proxy.get('enabled', True):
                    self.proxies.append(ProxyConfig(
                        address=proxy['address'],
                        type=proxy['type'],
                        timeout=proxy.get('timeout', 30),
                        enabled=True
                    ))
                    
            logger.info(f"已加载{len(self.proxies)}个代理配置")
            
        except Exception as e:
            logger.error(f"加载代理配置失败: {e}")
            raise
            
    def _test_proxy(self, proxy: ProxyConfig) -> bool:
        """测试代理是否可用。
        
        Args:
            proxy: 要测试的代理配置
            
        Returns:
            bool: 代理是否可用
        """
        # 检查缓存
        cache_key = f"{proxy.type}://{proxy.address}"
        if cache_key in self._proxy_status_cache:
            is_available, last_check_time = self._proxy_status_cache[cache_key]
            if time.time() - last_check_time < self._cache_ttl:
                logger.debug(f"使用缓存的代理状态: {cache_key} = {is_available}")
                return is_available
        
        try:
            # 首先测试代理服务器是否可连接
            host, port = proxy.address.split(':')
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(proxy.timeout)
            sock.connect((host, int(port)))
            sock.close()
            
            # 配置代理
            proxies = {
                'http': f"{proxy.type}://{proxy.address}",
                'https': f"{proxy.type}://{proxy.address}"
            }
            
            # 测试多个目标网站
            for url in self.TEST_URLS:
                try:
                    response = requests.get(
                        url,
                        proxies=proxies,
                        timeout=proxy.timeout,
                        verify=False  # 忽略SSL证书验证
                    )
                    if response.status_code == 200:
                        # 更新缓存
                        self._proxy_status_cache[cache_key] = (True, time.time())
                        logger.info(f"代理测试成功: {cache_key}")
                        return True
                except requests.RequestException as e:
                    logger.debug(f"测试URL {url} 失败: {e}")
                    continue
            
            # 所有URL都测试失败
            self._proxy_status_cache[cache_key] = (False, time.time())
            return False
            
        except Exception as e:
            logger.warning(f"代理测试失败 {proxy.address}: {e}")
            self._proxy_status_cache[cache_key] = (False, time.time())
            return False
            
    def get_current_proxy(self) -> Optional[str]:
        """获取当前可用的代理地址。
        
        如果当前代理不可用，会自动切换到下一个代理。
        最多重试3次，如果所有代理都不可用，返回None。
        
        Returns:
            Optional[str]: 代理地址，格式为"type://address"，如果没有可用代理则返回None
        """
        if not self.proxies:
            logger.warning("没有配置代理服务器")
            return None
            
        # 尝试所有代理
        original_index = self.current_index
        tried_count = 0
        
        while tried_count < len(self.proxies):
            current_proxy = self.proxies[self.current_index]
            proxy_url = f"{current_proxy.type}://{current_proxy.address}"
            
            logger.info(f"正在测试代理: {proxy_url}")
            if self._test_proxy(current_proxy):
                logger.info(f"找到可用代理: {proxy_url}")
                return proxy_url
                
            # 切换到下一个代理
            self.current_index = (self.current_index + 1) % len(self.proxies)
            tried_count += 1
            
        logger.error("所有代理都不可用")
        return None
        
    def add_proxy(self, address: str, proxy_type: str = "http", 
                 timeout: int = 30) -> None:
        """添加新的代理配置。
        
        Args:
            address: 代理服务器地址
            proxy_type: 代理类型，默认为http
            timeout: 超时时间，默认30秒
        """
        proxy = ProxyConfig(address=address, type=proxy_type, 
                          timeout=timeout, enabled=True)
        
        # 测试新代理是否可用
        if self._test_proxy(proxy):
            self.proxies.append(proxy)
            self._save_config()
            logger.info(f"成功添加新代理: {proxy_type}://{address}")
        else:
            logger.warning(f"新代理不可用，未添加: {proxy_type}://{address}")
        
    def _save_config(self) -> None:
        """保存代理配置到文件。"""
        config = {
            'proxies': [
                {
                    'address': p.address,
                    'type': p.type,
                    'timeout': p.timeout,
                    'enabled': p.enabled
                }
                for p in self.proxies
            ]
        }
        
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config, f, allow_unicode=True)
                
        except Exception as e:
            logger.error(f"保存代理配置失败: {e}")
            raise

# 创建全局代理管理器实例
proxy_manager = ProxyManager()

def get_current_proxy() -> Optional[str]:
    """获取当前代理设置。
    
    Returns:
        Optional[str]: 代理服务器地址，如果未设置则返回None
    """
    return os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") 