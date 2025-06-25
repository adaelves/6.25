"""测试mock工具模块。

提供用于测试的mock对象和工具函数。
"""

import time
import json
from typing import Any, Dict, Optional
from requests.exceptions import Timeout, RequestException

class MockResponse:
    """Mock的requests响应对象。
    
    Attributes:
        status_code: HTTP状态码
        elapsed: 请求耗时
        _json: JSON响应数据
        text: 文本响应数据
    """
    
    def __init__(
        self, 
        status_code: int = 200,
        json_data: Optional[Dict[str, Any]] = None,
        text: Optional[str] = None,
        delay: float = 0
    ):
        """初始化Mock响应。
        
        Args:
            status_code: HTTP状态码
            json_data: JSON响应数据
            text: 文本响应数据
            delay: 模拟的响应延迟（秒）
        """
        self.status_code = status_code
        self._json = json_data
        self.text = text or ""
        self.elapsed = self._simulate_delay(delay)
        
    def json(self) -> Dict[str, Any]:
        """返回JSON响应数据。
        
        Returns:
            Dict[str, Any]: JSON数据
            
        Raises:
            json.JSONDecodeError: JSON解析失败
        """
        if self._json is None:
            raise json.JSONDecodeError("Invalid JSON", self.text, 0)
        return self._json
        
    def raise_for_status(self):
        """检查响应状态码。
        
        Raises:
            RequestException: 状态码不是2xx
        """
        if self.status_code >= 400:
            raise RequestException(f"HTTP {self.status_code}")
            
    def _simulate_delay(self, delay: float) -> float:
        """模拟网络延迟。
        
        Args:
            delay: 延迟时间（秒）
            
        Returns:
            float: 实际延迟时间
            
        Raises:
            Timeout: 延迟超过超时时间
        """
        if delay > 3:  # 超过3秒视为超时
            raise Timeout(f"Request timed out after {delay} seconds")
            
        if delay > 0:
            time.sleep(delay)
            
        return delay

def create_video_response(
    title: str = "测试视频",
    bvid: str = "BV1xx411c7mD",
    duration: int = 180,
    author: str = "测试UP主",
    play_count: int = 1000,
    status_code: int = 200,
    delay: float = 0
) -> MockResponse:
    """创建视频信息的mock响应。
    
    Args:
        title: 视频标题
        bvid: BV号
        duration: 视频时长（秒）
        author: UP主名称
        play_count: 播放量
        status_code: HTTP状态码
        delay: 响应延迟（秒）
        
    Returns:
        MockResponse: Mock的响应对象
    """
    json_data = {
        "code": 0 if status_code < 400 else -1,
        "data": {
            "bvid": bvid,
            "title": title,
            "duration": duration,
            "owner": {
                "name": author
            },
            "stat": {
                "view": play_count
            }
        }
    }
    
    if status_code >= 400:
        json_data["message"] = "请求失败"
        
    return MockResponse(
        status_code=status_code,
        json_data=json_data,
        delay=delay
    ) 