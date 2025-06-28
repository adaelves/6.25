"""Twitter API客户端模块。

提供Twitter API的访问功能。
支持认证和代理。
"""

import logging
from typing import Optional, Dict, Any, List
import requests
from urllib.parse import urljoin
import json
import time

from src.core.exceptions import APIError
from src.utils.cookie_manager import CookieManager

logger = logging.getLogger(__name__)

class TwitterAPIClient:
    """Twitter API客户端。
    
    处理Twitter API的调用，支持认证和代理。
    实现自动重试和错误处理。
    """
    
    BASE_URL = "https://api.twitter.com/2/"
    
    def __init__(
        self,
        cookie_manager: Optional[CookieManager] = None,
        proxy: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """初始化API客户端。

        Args:
            cookie_manager: Cookie管理器
            proxy: 代理服务器
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
        """
        self.cookie_manager = cookie_manager
        self.proxy = proxy
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """创建请求会话。

        Returns:
            requests.Session: 配置好的会话对象
        """
        session = requests.Session()
        
        # 设置代理
        if self.proxy:
            session.proxies = {
                "http": self.proxy,
                "https": self.proxy
            }
            
        # 设置Cookie
        if self.cookie_manager:
            cookies = self.cookie_manager.get_cookies("twitter")
            if cookies:
                session.cookies.update(cookies)
                
        # 设置请求头
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Twitter-Active-User": "yes",
            "X-Twitter-Client-Language": "en"
        })
        
        return session
        
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        **kwargs
    ) -> Dict:
        """发送API请求。

        Args:
            method: 请求方法
            endpoint: API端点
            params: URL参数
            data: 请求数据
            **kwargs: 其他参数

        Returns:
            Dict: API响应

        Raises:
            APIError: API调用失败
        """
        url = urljoin(self.BASE_URL, endpoint)
        retries = 0
        
        while retries <= self.max_retries:
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data,
                    timeout=self.timeout,
                    **kwargs
                )
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                retries += 1
                if retries > self.max_retries:
                    raise APIError(f"API请求失败: {str(e)}")
                    
                # 指数退避重试
                time.sleep(2 ** retries)
                
    def download_tweet(self, tweet_id: str) -> Dict[str, Any]:
        """下载单条推文。

        Args:
            tweet_id: 推文ID

        Returns:
            Dict[str, Any]: 推文信息和媒体内容

        Raises:
            APIError: 下载失败
        """
        try:
            # 获取推文信息
            response = self._request(
                "GET",
                f"tweets/{tweet_id}",
                params={
                    "expansions": "attachments.media_keys",
                    "media.fields": "url,variants,type"
                }
            )
            
            if not response.get("data"):
                raise APIError("推文不存在或已删除")
                
            # 提取媒体信息
            media = []
            if "includes" in response and "media" in response["includes"]:
                for item in response["includes"]["media"]:
                    if item["type"] == "video":
                        # 获取最高质量的视频
                        variants = sorted(
                            item["variants"],
                            key=lambda x: x.get("bitrate", 0),
                            reverse=True
                        )
                        if variants:
                            media.append({
                                "type": "video",
                                "url": variants[0]["url"]
                            })
                    elif item["type"] in ["photo", "animated_gif"]:
                        media.append({
                            "type": item["type"],
                            "url": item["url"]
                        })
                        
            return {
                "type": "tweet",
                "id": tweet_id,
                "text": response["data"]["text"],
                "media": media
            }
            
        except Exception as e:
            raise APIError(f"下载推文失败: {str(e)}")
            
    def get_user_tweets(
        self,
        username: str,
        cursor: Optional[str] = None,
        count: int = 20
    ) -> Dict[str, Any]:
        """获取用户推文列表。

        Args:
            username: 用户名
            cursor: 分页游标
            count: 每页数量

        Returns:
            Dict[str, Any]: 推文列表和下一页游标

        Raises:
            APIError: 获取失败
        """
        try:
            # 获取用户ID
            user = self._request(
                "GET",
                "users/by/username/" + username
            )
            
            if not user.get("data"):
                raise APIError("用户不存在")
                
            user_id = user["data"]["id"]
            
            # 获取推文列表
            params = {
                "max_results": count,
                "expansions": "attachments.media_keys",
                "media.fields": "url,variants,type",
                "tweet.fields": "created_at,public_metrics"
            }
            
            if cursor:
                params["pagination_token"] = cursor
                
            response = self._request(
                "GET",
                f"users/{user_id}/tweets",
                params=params
            )
            
            tweets = []
            for tweet in response.get("data", []):
                tweets.append({
                    "id": tweet["id"],
                    "url": f"https://twitter.com/{username}/status/{tweet['id']}",
                    "text": tweet["text"],
                    "created_at": tweet["created_at"]
                })
                
            return {
                "tweets": tweets,
                "next_cursor": response.get("meta", {}).get("next_token")
            }
            
        except Exception as e:
            raise APIError(f"获取推文列表失败: {str(e)}") 