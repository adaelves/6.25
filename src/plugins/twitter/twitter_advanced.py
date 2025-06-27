"""Twitter高级下载器模块。

使用Playwright实现更强大的Twitter媒体下载功能。
支持图片和视频提取，以及频道批量下载。
"""

import time
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse, urljoin

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
import requests

from src.utils.cookie_manager import CookieManager
from .config import TwitterDownloaderConfig

logger = logging.getLogger(__name__)

class TwitterAdvancedDownloader:
    """Twitter高级下载器。
    
    使用Playwright实现更强大的媒体下载功能。
    支持图片和视频提取，以及频道批量下载。
    """
    
    def __init__(
        self,
        config: TwitterDownloaderConfig,
        cookie_manager: Optional[CookieManager] = None,
        headless: bool = True
    ):
        """初始化下载器。
        
        Args:
            config: 下载器配置
            cookie_manager: Cookie管理器
            headless: 是否使用无头模式
        """
        self.config = config
        self.cookie_manager = cookie_manager or CookieManager()
        self.headless = headless
        
        # 初始化Playwright
        self.playwright = sync_playwright().start()
        
        # 浏览器配置
        browser_args = []
        if self.config.proxy:
            browser_args.append(f'--proxy-server={self.config.proxy}')
        
        # 启动浏览器
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            args=browser_args
        )
        
        # 创建上下文
        self.context = self._create_context()
        
        # 下载记录
        self.downloaded_path = Path("config/downloaded.json")
        self.downloaded_ids = self._load_downloaded_ids()
        
    def _create_context(self) -> BrowserContext:
        """创建浏览器上下文。
        
        Returns:
            BrowserContext: 浏览器上下文
        """
        # 基本配置
        context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            ignore_https_errors=True
        )
        
        # 添加Cookie
        cookies = self.cookie_manager.get_cookies("twitter")
        if cookies:
            cookie_list = []
            for name, value in cookies.items():
                cookie_list.append({
                    'name': name,
                    'value': value,
                    'domain': '.twitter.com',
                    'path': '/'
                })
            context.add_cookies(cookie_list)
            
        return context
        
    def _load_downloaded_ids(self) -> Set[str]:
        """加载已下载的推文ID。
        
        Returns:
            Set[str]: 已下载推文ID集合
        """
        try:
            if self.downloaded_path.exists():
                with open(self.downloaded_path, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            return set()
        except Exception as e:
            logger.error(f"加载已下载记录失败: {e}")
            return set()
            
    def _save_downloaded_ids(self) -> None:
        """保存已下载的推文ID。"""
        try:
            self.downloaded_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.downloaded_path, 'w', encoding='utf-8') as f:
                json.dump(list(self.downloaded_ids), f)
        except Exception as e:
            logger.error(f"保存已下载记录失败: {e}")
            
    def extract_media(self, tweet_url: str) -> Dict[str, List[str]]:
        """提取推文中的媒体URL。
        
        Args:
            tweet_url: 推文URL
            
        Returns:
            Dict[str, List[str]]: 包含图片和视频URL的字典
        """
        # 统一使用twitter.com域名
        tweet_url = tweet_url.replace('x.com', 'twitter.com')
        
        page = self.context.new_page()
        try:
            logger.info(f"开始提取媒体: {tweet_url}")
            
            # 访问推文页面
            page.goto(tweet_url, wait_until='networkidle', timeout=60000)
            
            # 等待推文加载
            page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
            
            # 提取图片
            img_elements = page.query_selector_all('img[src*="twimg.com/media"]')
            img_urls = []
            for img in img_elements:
                src = img.get_attribute("src")
                if src:
                    # 获取最高质量的图片
                    base_url = src.split('?')[0]
                    img_urls.append(f"{base_url}?format=jpg&name=orig")
            img_urls = list(set(img_urls))  # 去重
            
            # 提取视频
            video_elements = page.query_selector_all('video source')
            video_urls = []
            for video in video_elements:
                src = video.get_attribute("src")
                if src:
                    video_urls.append(src)
                    
            # 如果没有找到媒体，尝试从API获取
            if not img_urls and not video_urls:
                logger.info("从页面未找到媒体，尝试使用API...")
                media = self._extract_media_from_api(tweet_url)
                img_urls.extend(media['images'])
                video_urls.extend(media['videos'])
                
            logger.info(f"找到 {len(img_urls)} 张图片, {len(video_urls)} 个视频")
            
            return {
                'images': img_urls,
                'videos': video_urls
            }
            
        except Exception as e:
            logger.error(f"提取媒体失败: {e}")
            return {'images': [], 'videos': []}
            
        finally:
            page.close()
            
    def _extract_media_from_api(self, tweet_url: str) -> Dict[str, List[str]]:
        """从API提取媒体URL。
        
        Args:
            tweet_url: 推文URL
            
        Returns:
            Dict[str, List[str]]: 包含图片和视频URL的字典
        """
        tweet_id = tweet_url.split('/status/')[-1].split('?')[0]
        
        # 获取认证信息
        cookies = self.cookie_manager.get_cookies("twitter")
        if not cookies:
            return {'images': [], 'videos': []}
            
        auth_token = cookies.get('auth_token', '')
        ct0 = cookies.get('ct0', '')
        
        # API请求
        api_url = "https://twitter.com/i/api/graphql/2ICDjqPd81tulZcYrtpTuQ/TweetResultByRestId"
        
        variables = {
            "tweetId": tweet_id,
            "withCommunity": False,
            "includePromotedContent": False,
            "withVoice": False
        }
        
        features = {
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "tweetypie_unmention_optimization_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": False,
            "tweet_awards_web_tipping_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "responsive_web_media_download_video_enabled": False,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_enhance_cards_enabled": False
        }
        
        headers = {
            'Authorization': f'Bearer {auth_token}',
            'x-csrf-token': ct0,
            'Cookie': f'auth_token={auth_token}; ct0={ct0}',
            'x-twitter-auth-type': 'OAuth2Session',
            'x-twitter-client-language': 'en',
            'x-twitter-active-user': 'yes'
        }
        
        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(features)
        }
        
        try:
            response = requests.get(
                api_url,
                params=params,
                headers=headers,
                proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            images = []
            videos = []
            
            tweet_data = data.get('data', {}).get('tweet', {})
            if 'legacy' in tweet_data:
                legacy = tweet_data['legacy']
                if 'extended_entities' in legacy and 'media' in legacy['extended_entities']:
                    for media in legacy['extended_entities']['media']:
                        if media['type'] == 'photo':
                            img_url = media.get('media_url_https', '')
                            if img_url:
                                img_url = f"{img_url}?format=jpg&name=orig"
                                images.append(img_url)
                        elif media['type'] == 'video':
                            variants = media.get('video_info', {}).get('variants', [])
                            # 获取最高质量的视频
                            max_bitrate = 0
                            best_video_url = None
                            for variant in variants:
                                if variant.get('content_type') == 'video/mp4':
                                    bitrate = variant.get('bitrate', 0)
                                    if bitrate > max_bitrate:
                                        max_bitrate = bitrate
                                        best_video_url = variant.get('url')
                            if best_video_url:
                                videos.append(best_video_url)
                                
            return {
                'images': images,
                'videos': videos
            }
            
        except Exception as e:
            logger.error(f"API提取媒体失败: {e}")
            return {'images': [], 'videos': []}
            
    def download_channel(
        self,
        profile_url: str,
        max_tweets: int = 50,
        scroll_interval: int = 2
    ) -> List[str]:
        """下载用户频道的所有媒体。
        
        Args:
            profile_url: 用户主页URL
            max_tweets: 最大推文数
            scroll_interval: 滚动间隔（秒）
            
        Returns:
            List[str]: 推文ID列表
        """
        # 统一使用twitter.com域名
        profile_url = profile_url.replace('x.com', 'twitter.com')
        
        page = self.context.new_page()
        try:
            logger.info(f"开始获取用户推文: {profile_url}")
            
            # 访问用户主页
            page.goto(profile_url, wait_until='networkidle', timeout=60000)
            
            # 等待推文加载
            page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
            
            # 模拟滚动加载
            tweet_ids = set()
            no_new_tweets_count = 0
            last_height = 0
            
            while len(tweet_ids) < max_tweets and no_new_tweets_count < 3:
                # 获取当前推文
                initial_count = len(tweet_ids)
                tweets = page.query_selector_all('article[data-testid="tweet"]')
                
                for tweet in tweets:
                    # 提取推文ID
                    tweet_link = tweet.query_selector('a[href*="/status/"]')
                    if tweet_link:
                        href = tweet_link.get_attribute('href')
                        tweet_id = href.split('/status/')[-1]
                        if tweet_id not in self.downloaded_ids:
                            tweet_ids.add(tweet_id)
                            
                        if len(tweet_ids) >= max_tweets:
                            break
                            
                # 检查是否有新推文
                if len(tweet_ids) == initial_count:
                    no_new_tweets_count += 1
                    logger.debug(f"未发现新推文，计数: {no_new_tweets_count}")
                else:
                    no_new_tweets_count = 0
                    
                # 滚动到底部
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(scroll_interval)
                
                # 检查是否到达底部
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    logger.debug("已到达页面底部")
                    break
                last_height = new_height
                
            logger.info(f"找到 {len(tweet_ids)} 条未下载推文")
            return list(tweet_ids)
            
        except Exception as e:
            logger.error(f"获取用户推文失败: {e}")
            return []
            
        finally:
            page.close()
            
    def download_media(self, url: str, save_dir: Path) -> bool:
        """下载媒体文件。
        
        Args:
            url: 媒体URL
            save_dir: 保存目录
            
        Returns:
            bool: 是否下载成功
        """
        try:
            # 创建保存目录
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 获取文件名
            filename = urlparse(url).path.split('/')[-1].split('?')[0]
            save_path = save_dir / filename
            
            # 下载文件
            response = requests.get(
                url,
                proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                timeout=30,
                stream=True
            )
            response.raise_for_status()
            
            # 保存文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
            logger.info(f"媒体已保存: {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"下载媒体失败 {url}: {e}")
            return False
            
    def __del__(self):
        """清理资源。"""
        try:
            self.browser.close()
            self.playwright.stop()
        except:
            pass 