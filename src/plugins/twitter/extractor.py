"""Twitter信息提取模块。"""

import re
import json
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class TwitterExtractor:
    """Twitter信息提取器。
    
    用于从Twitter URL中提取媒体信息。
    
    Attributes:
        proxy: Optional[str], 代理服务器
        timeout: float, 超时时间
    """
    
    # API 端点
    API_BASE = "https://twitter.com/i/api/graphql"
    TWEET_DETAIL_QUERY = "k5XapwcY5qKVX7gYFdkFMA"  # TweetDetail query hash
    
    def __init__(self, proxy: Optional[str] = None, timeout: float = 30.0):
        """初始化提取器。
        
        Args:
            proxy: 代理服务器
            timeout: 超时时间
        """
        self.proxy = proxy
        self.timeout = timeout
        self.session = requests.Session()
        
        # 设置默认请求头
        self.session.headers.update({
            "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://twitter.com/",
            "Origin": "https://twitter.com",
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2",
            "x-twitter-client-language": "en",
            "x-csrf-token": "a8e0c6d5f7b3e2d1",  # 随机生成的CSRF令牌
            "Cookie": "ct0=a8e0c6d5f7b3e2d1"  # 与CSRF令牌匹配
        })
        
        # 设置代理
        if proxy:
            self.session.proxies = {
                "http": proxy,
                "https": proxy
            }
        
    def extract_info(self, url: str) -> Dict[str, Any]:
        """提取推文信息。
        
        Args:
            url: 推文URL
            
        Returns:
            Dict[str, Any]: 包含以下信息的字典：
                - id: str, 推文ID
                - author: str, 作者用户名
                - created_at: str, 创建时间
                - text: str, 推文内容
                - likes: int, 点赞数
                - reposts: int, 转发数
                - media_urls: List[str], 媒体URL列表
                
        Raises:
            ValueError: URL无效
            requests.RequestException: 请求失败
        """
        # 提取推文ID
        match = re.match(r"https://twitter\.com/(\w+)/status/(\d+)", url)
        if not match:
            raise ValueError("无效的Twitter URL")
            
        username, tweet_id = match.groups()
        logger.info(f"提取推文信息: {username}/{tweet_id}")
        
        try:
            # 构造GraphQL查询
            variables = {
                "focalTweetId": tweet_id,
                "with_rux_injections": False,
                "includePromotedContent": False,
                "withCommunity": False,
                "withQuickPromoteEligibilityTweetFields": False,
                "withBirdwatchNotes": False,
                "withVoice": True,
                "withV2Timeline": True
            }
            
            # 发送请求
            response = self.session.get(
                f"{self.API_BASE}/{self.TWEET_DETAIL_QUERY}/TweetDetail",
                params={
                    "variables": json.dumps(variables),
                    "features": json.dumps({
                        "responsive_web_graphql_exclude_directive_enabled": True,
                        "verified_phone_label_enabled": False,
                        "creator_subscriptions_tweet_preview_api_enabled": True,
                        "responsive_web_graphql_timeline_navigation_enabled": True,
                        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                        "tweetypie_unmention_optimization_enabled": True,
                        "vibe_api_enabled": True,
                        "responsive_web_edit_tweet_api_enabled": True,
                        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                        "view_counts_everywhere_api_enabled": True,
                        "longform_notetweets_consumption_enabled": True,
                        "tweet_awards_web_tipping_enabled": False,
                        "freedom_of_speech_not_reach_fetch_enabled": True,
                        "standardized_nudges_misinfo": True,
                        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
                        "interactive_text_enabled": True,
                        "responsive_web_text_conversations_enabled": False,
                        "longform_notetweets_rich_text_read_enabled": True,
                        "responsive_web_enhance_cards_enabled": False
                    })
                },
                timeout=self.timeout,
                verify=False  # 禁用SSL验证以便调试
            )
            response.raise_for_status()
            
            # 解析响应
            data = response.json()
            logger.debug(f"API响应: {json.dumps(data, indent=2)}")
            
            # 提取推文数据
            tweet_result = data["data"]["threaded_conversation_with_injections"]["instructions"][0]["entries"][0]["content"]["itemContent"]["tweet_results"]["result"]
            tweet = tweet_result["legacy"]
            user = tweet_result["core"]["user_results"]["result"]["legacy"]
            
            # 提取媒体URL
            media_urls = []
            if "extended_entities" in tweet and "media" in tweet["extended_entities"]:
                for media in tweet["extended_entities"]["media"]:
                    if media["type"] == "photo":
                        media_urls.append(media["media_url_https"])
                    elif media["type"] == "video":
                        variants = media["video_info"]["variants"]
                        video_variants = [v for v in variants if v["content_type"] == "video/mp4"]
                        if video_variants:
                            best_variant = max(
                                video_variants,
                                key=lambda x: x.get("bitrate", 0)
                            )
                            media_urls.append(best_variant["url"])
            
            # 构造返回数据
            return {
                "id": tweet_id,
                "author": user["screen_name"],
                "created_at": tweet["created_at"],
                "text": tweet["full_text"],
                "likes": tweet["favorite_count"],
                "reposts": tweet["retweet_count"],
                "media_urls": media_urls
            }
            
        except requests.RequestException as e:
            logger.error(f"获取推文信息失败: {e}")
            raise
            
        except (KeyError, ValueError) as e:
            logger.error(f"解析推文信息失败: {e}")
            raise ValueError(f"解析推文信息失败: {e}")
            
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息。
        
        Args:
            url: 视频URL
            
        Returns:
            Dict[str, Any]: 包含视频信息的字典
        """
        info = self.extract_info(url)
        video_urls = [url for url in info["media_urls"] if url.endswith(".mp4")]
        if not video_urls:
            raise ValueError("未找到视频内容")
            
        return {
            "title": info["text"],
            "author": info["author"],
            "url": video_urls[0],
            "created_at": info["created_at"]
        } 