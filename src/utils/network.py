"""网络工具。

提供网络请求相关的工具类。
"""

import logging
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from urllib.parse import urlparse

from ..exceptions import NetworkError, RateLimitError

logger = logging.getLogger(__name__)

class NetworkSession:
    """网络会话。
    
    提供以下功能：
    1. 自动重试
    2. 代理支持
    3. 超时控制
    4. 请求头管理
    
    Attributes:
        session: requests会话
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
    """
    
    # 默认请求头
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    def __init__(
        self,
        proxy: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None
    ):
        """初始化会话。
        
        Args:
            proxy: 代理地址，可选
            timeout: 超时时间，默认30秒
            max_retries: 最大重试次数，默认3次
            headers: 自定义请求头，可选
        """
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 设置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 设置请求头
        self.session.headers.update(self.DEFAULT_HEADERS)
        if headers:
            self.session.headers.update(headers)
            
        # 设置代理
        if proxy:
            self.set_proxy(proxy)
            
    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> requests.Response:
        """发送GET请求。
        
        Args:
            url: 请求URL
            params: 查询参数，可选
            **kwargs: 其他参数
            
        Returns:
            requests.Response: 响应对象
            
        Raises:
            NetworkError: 网络错误
            RateLimitError: 请求频率限制
        """
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
                **kwargs
            )
            
            # 检查响应状态
            response.raise_for_status()
            
            # 检查频率限制
            if response.status_code == 429:
                raise RateLimitError(
                    f"Rate limit exceeded: {response.text}"
                )
                
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GET request failed: {e}")
            raise NetworkError(f"GET request failed: {e}")
            
    def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> requests.Response:
        """发送POST请求。
        
        Args:
            url: 请求URL
            data: 表单数据，可选
            json: JSON数据，可选
            **kwargs: 其他参数
            
        Returns:
            requests.Response: 响应对象
            
        Raises:
            NetworkError: 网络错误
            RateLimitError: 请求频率限制
        """
        try:
            response = self.session.post(
                url,
                data=data,
                json=json,
                timeout=self.timeout,
                **kwargs
            )
            
            # 检查响应状态
            response.raise_for_status()
            
            # 检查频率限制
            if response.status_code == 429:
                raise RateLimitError(
                    f"Rate limit exceeded: {response.text}"
                )
                
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"POST request failed: {e}")
            raise NetworkError(f"POST request failed: {e}")
            
    def set_proxy(self, proxy: str):
        """设置代理。
        
        Args:
            proxy: 代理地址
        """
        parsed = urlparse(proxy)
        if not parsed.scheme:
            proxy = f"http://{proxy}"
            
        self.session.proxies = {
            'http': proxy,
            'https': proxy
        }
        
    def set_header(self, key: str, value: str):
        """设置请求头。
        
        Args:
            key: 请求头名称
            value: 请求头值
        """
        self.session.headers[key] = value
        
    def clear_headers(self):
        """清除所有请求头。"""
        self.session.headers.clear()
        self.session.headers.update(self.DEFAULT_HEADERS) 