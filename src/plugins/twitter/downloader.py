"""Twitter视频下载器模块。

该模块负责从Twitter下载视频和图片。
支持API和浏览器混合下载模式。
"""

import os
import logging
import json
from typing import Optional, Dict, Any, List, Callable, Generator, Tuple, Set
from pathlib import Path
import yt_dlp
from datetime import datetime
import time
from tqdm import tqdm
import re
import requests
from urllib.parse import urlparse
import hashlib
import random
from bs4 import BeautifulSoup
from ratelimit import limits, sleep_and_retry

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError, APIError, RateLimitException
from src.utils.cookie_manager import CookieManager
from .config import TwitterDownloaderConfig
from .api_client import TwitterAPIClient

logger = logging.getLogger(__name__)

class TwitterDownloader(BaseDownloader):
    """Twitter视频下载器。
    
    支持会员视频下载和字幕下载。
    自动处理年龄限制和会员限制。
    
    Attributes:
        config: TwitterDownloaderConfig, 下载器配置
        api_client: TwitterAPIClient, API客户端
    """
    
    # CDN镜像列表
    CDN_MIRRORS = [
        "pbs.twimg.com",  # 官方CDN
        "twimg1.sinaimg.cn",  # 新浪CDN
        "twimg2.sinaimg.cn",
        "twimg3.sinaimg.cn",
        "twimg.example-cdn.com"  # 示例CDN
    ]
    
    # 请求头列表
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
    ]

    def __init__(
        self,
        config: TwitterDownloaderConfig,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cookie_manager: Optional[CookieManager] = None
    ):
        """初始化下载器。

        Args:
            config: 下载器配置
            progress_callback: 进度回调函数
            cookie_manager: Cookie管理器
        """
        super().__init__(
            platform="twitter",
            save_dir=config.save_dir,
            progress_callback=progress_callback,
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cookie_manager=cookie_manager,
            config=config
        )
        
        # 初始化API客户端
        self.api_client = TwitterAPIClient(
            cookie_manager=cookie_manager,
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries
        )
        
        # 设置yt-dlp
        self._setup_yt_dlp()
        
        # 初始化会话
        self.session = self._create_session()
        
        # 初始化去重缓存
        self._dedup_cache: Set[Tuple[str, str]] = set()

    def _setup_yt_dlp(self):
        """设置yt-dlp下载器。"""
        self.yt_dlp_opts = {
            # 基本配置
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best/jpg/png',  # 添加图片格式支持
            'outtmpl': os.path.join(str(self.config.save_dir), self.config.output_template),
            
            # 提取设置
            'extract_flat': False,
            'ignoreerrors': True,
            'no_warnings': True,
            'quiet': True,
            
            # 网络设置
            'nocheckcertificate': True,
            'proxy': self.config.proxy,
            'socket_timeout': self.config.timeout,
            'retries': self.config.max_retries,
            
            # 回调函数
            'progress_hooks': [self._progress_hook],
            'postprocessor_hooks': [self._postprocessor_hook],
            
            # Twitter特定设置
            'extractor_args': {
                'twitter': {
                    'api': ['graphql'],
                }
            },
            
            # 媒体处理设置
            'writethumbnail': True,
            'writesubtitles': True,
            'merge_output_format': 'mp4',
            
            # 图片下载设置
            'extract_flat': 'in_playlist',
            'download_archive': os.path.join(str(self.config.save_dir), '.download_archive'),
            'playlist_items': '1:',
            
            # 额外设置
            'add_metadata': True,
            'embed_thumbnail': True,
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }]
        }

        # 添加Cookie文件
        if self.cookie_manager:
            cookie_file = self.cookie_manager.get_cookie_file("twitter")
            if os.path.exists(cookie_file):
                self.yt_dlp_opts['cookiefile'] = cookie_file

    def _progress_hook(self, d: Dict[str, Any]):
        """下载进度回调。

        Args:
            d: 进度信息
        """
        try:
            if d['status'] == 'downloading':
                # 计算下载进度
                progress = 0.0
                desc = f"下载中: {d['filename']}"
                
                if 'total_bytes' in d and d['total_bytes']:
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d['total_bytes']
                    progress = downloaded / total
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    
                    if speed:
                        desc += f" - {speed/1024/1024:.1f}MB/s"
                    if eta:
                        desc += f" - 剩余{eta}秒"
                
                # 更新进度条
                if not hasattr(self, '_pbar'):
                    self._pbar = tqdm(total=100, desc=desc, unit='%')
                self._pbar.n = int(progress * 100)
                self._pbar.set_description(desc)
                self._pbar.refresh()

                # 调用进度回调
                if self.progress_callback:
                    self.progress_callback(progress, desc)

            elif d['status'] == 'finished':
                if hasattr(self, '_pbar'):
                    self._pbar.close()
                    delattr(self, '_pbar')
                logger.info(f"下载完成: {d['filename']}")
                if self.progress_callback:
                    self.progress_callback(1.0, "下载完成")

            elif d['status'] == 'error':
                if hasattr(self, '_pbar'):
                    self._pbar.close()
                    delattr(self, '_pbar')
                error_msg = f"下载出错: {d.get('error', '未知错误')}"
                logger.error(error_msg)
                if self.progress_callback:
                    self.progress_callback(0.0, error_msg)
                    
        except Exception as e:
            logger.error(f"处理进度回调时出错: {str(e)}")
            if self.progress_callback:
                self.progress_callback(0.0, f"进度更新出错: {str(e)}")

    def _postprocessor_hook(self, d: Dict[str, Any]):
        """后处理回调。

        Args:
            d: 处理信息
        """
        try:
            if d['status'] == 'started':
                msg = f"开始处理: {d.get('postprocessor', '')}"
                logger.info(msg)
                if self.progress_callback:
                    self.progress_callback(0.0, msg)
                    
            elif d['status'] == 'finished':
                msg = f"处理完成: {d.get('postprocessor', '')}"
                logger.info(msg)
                if self.progress_callback:
                    self.progress_callback(1.0, msg)
                    
            elif d['status'] == 'error':
                error_msg = f"处理出错: {d.get('error', '未知错误')}"
                logger.error(error_msg)
                if self.progress_callback:
                    self.progress_callback(0.0, error_msg)
                    
        except Exception as e:
            logger.error(f"处理后处理回调时出错: {str(e)}")
            if self.progress_callback:
                self.progress_callback(0.0, f"处理更新出错: {str(e)}")

    def _validate_url(self, url: str) -> bool:
        """验证URL是否为有效的Twitter链接。

        Args:
            url: 要验证的URL

        Returns:
            bool: 是否为有效的Twitter链接
        """
        url = self._normalize_url(url)
        return 'twitter.com' in url or 'x.com' in url

    def _extract_tweet_id(self, url: str) -> str:
        """从URL中提取推文ID。

        Args:
            url: 推文URL

        Returns:
            str: 推文ID
        """
        # 匹配推文ID的正则表达式
        pattern = r'/status/(\d+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        raise DownloadError("无法从URL中提取推文ID")

    def _get_tweet_api_url(self, tweet_id: str) -> str:
        """获取推文API URL。

        Args:
            tweet_id: 推文ID

        Returns:
            str: API URL
        """
        return f"https://api.twitter.com/2/tweets/{tweet_id}?expansions=attachments.media_keys&media.fields=url,variants"

    def _try_download_image_from_html(self, url: str) -> Dict[str, Any]:
        """尝试从HTML页面中提取并下载图片。

        Args:
            url: 推文URL

        Returns:
            Dict[str, Any]: 下载结果
        """
        try:
            # 发送请求获取页面内容
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            }

            # 规范化URL
            url = url.replace('x.com', 'twitter.com')
            if not url.startswith('http'):
                url = f'https://{url}'

            # 发送请求
            response = requests.get(
                url,
                headers=headers,
                proxies={'http': self.proxy, 'https': self.proxy} if self.proxy else None,
                timeout=30
            )
            response.raise_for_status()
            
            # 查找图片URL
            # 匹配Twitter图片URL的正则表达式
            image_patterns = [
                r'https://pbs\.twimg\.com/media/[^"\']+(?:jpg|png|jpeg)',  # 普通图片
                r'https://pbs\.twimg\.com/tweet_video_thumb/[^"\']+\.(?:jpg|png|jpeg)',  # GIF缩略图
                r'https://pbs\.twimg\.com/ext_tw_video_thumb/[^"\']+\.(?:jpg|png|jpeg)',  # 视频缩略图
                r'https://pbs\.twimg\.com/amplify_video_thumb/[^"\']+\.(?:jpg|png|jpeg)'  # 放大视频缩略图
            ]
            
            image_urls = set()
            for pattern in image_patterns:
                urls = re.findall(pattern, response.text)
                image_urls.update(urls)
            
            if not image_urls:
                return {'success': False, 'message': '未找到图片'}
            
            success_count = 0
            tweet_id = self._extract_tweet_id(url)
            
            for index, img_url in enumerate(image_urls):
                try:
                    # 确保使用最高质量的图片
                    img_url = img_url.split('?')[0]
                    if not img_url.endswith(('jpg', 'jpeg', 'png')):
                        img_url += '?format=jpg&name=4096x4096'
                    
                    # 生成保存路径
                    filename = f"{tweet_id}_{index + 1}.jpg"
                    save_path = os.path.join(str(self.config.save_dir), filename)
                    
                    # 下载图片
                    if self._download_image(img_url, save_path):
                        success_count += 1
                        logger.info(f"成功下载图片: {filename}")
                        
                except Exception as e:
                    logger.error(f"处理图片URL失败: {str(e)}")
                    continue
            
            return {
                'success': success_count > 0,
                'media_count': success_count,
                'url': url
            }
            
        except Exception as e:
            logger.error(f"从HTML获取图片失败: {str(e)}")
            return {'success': False, 'message': str(e)}

    def _download_image(self, url: str, save_path: str) -> bool:
        """下载图片。

        Args:
            url: 图片URL
            save_path: 保存路径

        Returns:
            bool: 是否下载成功
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://twitter.com/',
                'Connection': 'keep-alive'
            }
            
            response = requests.get(
                url,
                headers=headers,
                proxies={'http': self.proxy, 'https': self.proxy} if self.proxy else None,
                timeout=30,
                stream=True
            )
            response.raise_for_status()
            
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 保存图片
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
            
        except Exception as e:
            logger.error(f"下载图片失败: {str(e)}")
            return False

    def _get_guest_token(self) -> str:
        """获取Twitter访客令牌。

        Returns:
            str: 访客令牌
        """
        try:
            headers = {
                'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA'
            }
            response = requests.post(
                'https://api.twitter.com/1.1/guest/activate.json',
                headers=headers,
                proxies={'http': self.proxy, 'https': self.proxy} if self.proxy else None
            )
            response.raise_for_status()
            return response.json()['guest_token']
        except Exception as e:
            logger.error(f"获取访客令牌失败: {str(e)}")
            return ''

    def _extract_tweet_result(self, data: Dict) -> Optional[Dict]:
        """从GraphQL响应中提取推文数据。

        Args:
            data: GraphQL响应数据

        Returns:
            Optional[Dict]: 推文数据或None
        """
        try:
            instructions = data['data']['threaded_conversation_with_injections_v2']['instructions']
            for instruction in instructions:
                if instruction['type'] == 'TimelineAddEntries':
                    entries = instruction['entries']
                    for entry in entries:
                        if 'tweet_results' in entry['content']['itemContent']:
                            result = entry['content']['itemContent']['tweet_results']['result']
                            if 'tweet' in result:
                                return result['tweet']
                            return result
            return None
        except Exception:
            return None

    def _random_headers(self) -> Dict[str, str]:
        """生成随机请求头。
        
        Returns:
            Dict[str, str]: 请求头字典
        """
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'image/webp,*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://twitter.com/',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }

    @sleep_and_retry
    @limits(calls=50, period=900)  # 15分钟50次请求
    def _call_api(self, url: str) -> requests.Response:
        """调用Twitter API，带限流处理。
        
        Args:
            url: API URL
            
        Returns:
            requests.Response: API响应
            
        Raises:
            RateLimitException: 触发限流时抛出
        """
        response = self.session.get(
            url,
            headers=self._random_headers(),
            proxies=self._get_proxies(),
            timeout=self.config.timeout
        )
        
        if response.status_code == 429:
            reset_time = int(response.headers.get('x-rate-limit-reset', 300))
            logger.warning(f"触发Twitter API限流，将在{reset_time}秒后重试")
            time.sleep(reset_time + 5)  # 缓冲5秒
            raise RateLimitException("触发Twitter API限流")
            
        return response

    def _safe_hash_file(self, path: str) -> str:
        """内存安全的文件哈希计算。
        
        使用分块读取方式计算大文件的MD5哈希值，
        避免一次性读入整个文件导致内存溢出。
        
        Args:
            path: 文件路径
            
        Returns:
            str: 文件的MD5哈希值
        """
        md5 = hashlib.md5()
        with open(path, 'rb') as f:
            # 每次读取8KB
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()

    def _download_media(self, url: str, tweet_id: str = "") -> bytes:
        """下载媒体文件。
        
        Args:
            url: 媒体URL
            tweet_id: 推文ID
            
        Returns:
            bytes: 媒体内容
            
        Raises:
            DownloadError: 下载失败时抛出
        """
        try:
            # 使用限流保护的API调用
            response = self._call_api(url)
            response.raise_for_status()
            return response.content
            
        except RateLimitException:
            # 重试逻辑由装饰器处理
            raise
            
        except Exception as e:
            logger.error(f"下载媒体失败: {str(e)}")
            raise DownloadError(f"下载媒体失败: {str(e)}")

    def _calculate_media_hash(self, content: bytes) -> str:
        """计算媒体文件哈希值。
        
        Args:
            content: 媒体内容
            
        Returns:
            str: MD5哈希值
        """
        return hashlib.md5(content).hexdigest()

    def _remove_dupes(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """复合去重逻辑。
        
        基于推文ID和媒体文件哈希的组合去重。
        
        Args:
            items: 媒体项列表
            
        Returns:
            List[Dict[str, Any]]: 去重后的列表
        """
        unique_items = []
        seen_keys = set()
        
        for item in items:
            # 获取媒体内容
            try:
                content = self._download_media(item['url'], item.get('tweet_id', ''))
                media_hash = self._calculate_media_hash(content)
            except Exception as e:
                logger.error(f"计算媒体哈希失败: {str(e)}")
                continue
                
            # 构建去重键
            dedup_key = (item.get('tweet_id', ''), media_hash)
            
            # 检查是否重复
            if dedup_key not in seen_keys and dedup_key not in self._dedup_cache:
                seen_keys.add(dedup_key)
                self._dedup_cache.add(dedup_key)
                
                # 添加哈希信息
                item['media_hash'] = media_hash
                unique_items.append(item)
                
                logger.debug(f"添加新媒体: {item.get('tweet_id', 'unknown')} ({media_hash})")
            else:
                logger.info(f"跳过重复媒体: {item.get('tweet_id', 'unknown')} ({media_hash})")
                
                # 如果文件已存在，尝试删除
                if 'path' in item and os.path.exists(item['path']):
                    try:
                        os.remove(item['path'])
                        logger.info(f"删除重复文件: {item['path']}")
                    except Exception as e:
                        logger.warning(f"删除重复文件失败: {item['path']} - {str(e)}")
                        
        return unique_items

    def download(self, url: str) -> Dict[str, Any]:
        """下载Twitter内容。

        支持以下URL类型:
        - 单条推文: twitter.com/user/status/123
        - 用户主页: twitter.com/user
        - 列表页面: twitter.com/i/lists/123

        Args:
            url: Twitter URL

        Returns:
            Dict[str, Any]: 下载结果

        Raises:
            DownloadError: 下载失败
        """
        if not self._validate_url(url):
            raise DownloadError(f"无效的Twitter URL: {url}")

        url = self._normalize_url(url)
        
        try:
            if "/status/" in url:
                raw_result = self._download_tweet(url)
                if raw_result.get('media'):
                    # 使用复合去重逻辑
                    raw_result['media'] = self._remove_dupes(raw_result['media'])
                return raw_result
            elif "/i/lists/" in url:
                return self._download_list(url)
            else:
                return self._download_profile(url)
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            raise DownloadError(f"下载失败: {str(e)}")

    def _download_tweet(self, url: str) -> Dict[str, Any]:
        """下载单条推文。

        优先使用API下载，失败时降级到浏览器模拟。

        Args:
            url: 推文URL

        Returns:
            Dict[str, Any]: 下载结果
        """
        tweet_id = self._extract_tweet_id(url)
        
        try:
            # 优先尝试API下载
            logger.info("尝试使用API下载...")
            return self.api_client.download_tweet(tweet_id)
        except APIError as e:
            logger.info(f"API下载失败({str(e)})，降级到浏览器模拟...")
            return self._browser_download_tweet(url)

    def _download_profile(self, profile_url: str) -> Dict[str, Any]:
        """下载用户主页内容。

        使用分页方式获取推文列表。

        Args:
            profile_url: 用户主页URL

        Returns:
            Dict[str, Any]: 下载结果
        """
        username = self._extract_username(profile_url)
        results = []
        
        try:
            # 优先尝试API
            for page in self._api_get_tweets(username):
                results.extend(self._process_tweet_page(page))
                if self.config.max_items and len(results) >= self.config.max_items:
                    break
        except APIError:
            # 降级到浏览器模拟
            logger.info("API获取失败，降级到浏览器模拟...")
            for page in self._browser_get_tweets(profile_url):
                results.extend(self._process_tweet_page(page))
                if self.config.max_items and len(results) >= self.config.max_items:
                    break
        
        return {
            "type": "profile",
            "url": profile_url,
            "items": results[:self.config.max_items] if self.config.max_items else results
        }

    def _process_tweet_page(self, tweets: List[Dict]) -> List[Dict]:
        """处理一页推文。

        Args:
            tweets: 推文列表

        Returns:
            List[Dict]: 处理结果
        """
        results = []
        for tweet in tweets:
            try:
                result = self._download_tweet(tweet["url"])
                results.append(result)
                # 简化的日志输出
                logger.info(f"已下载: {tweet['url']}")
            except Exception as e:
                logger.warning(f"下载失败: {tweet['url']} - {str(e)}")
        return results

    def _api_get_tweets(self, username: str) -> Generator[List[Dict], None, None]:
        """使用API获取推文列表。

        Args:
            username: 用户名

        Yields:
            List[Dict]: 一页推文
        """
        cursor = None
        while True:
            try:
                page = self.api_client.get_user_tweets(
                    username,
                    cursor=cursor,
                    count=20
                )
                if not page["tweets"]:
                    break
                    
                yield page["tweets"]
                cursor = page.get("next_cursor")
                if not cursor:
                    break
                    
                # 简化的日志输出
                logger.info(f"已获取{len(page['tweets'])}条推文")
                
            except APIError as e:
                logger.error(f"API获取失败: {str(e)}")
                break

    def _browser_get_tweets(self, profile_url: str) -> Generator[List[Dict], None, None]:
        """使用浏览器模拟获取推文列表。

        Args:
            profile_url: 用户主页URL

        Yields:
            List[Dict]: 一页推文
        """
        page_num = 1
        while True:
            try:
                with self._get_browser_page() as page:
                    tweets = self._extract_page_tweets(page, profile_url)
                    if not tweets:
                        break
                        
                    yield tweets
                    
                    # 简化的日志输出
                    logger.info(f"已获取第{page_num}页")
                    page_num += 1
                    
                    if not self._has_next_page(page):
                        break
                        
            except Exception as e:
                logger.error(f"浏览器获取失败: {str(e)}")
                break

    def _normalize_url(self, url: str) -> str:
        """规范化Twitter URL。

        Args:
            url: 原始URL

        Returns:
            str: 规范化后的URL
        """
        # 将x.com转换为twitter.com
        url = url.replace('x.com', 'twitter.com')
        
        # 确保URL以https://开头
        if not url.startswith('http'):
            url = f'https://{url}'
            
        return url

class TwitterDownloaderRouter:
    """Twitter下载器路由。
    
    用于根据不同URL类型选择相应的下载方法。
    """
    
    def __init__(self, config: TwitterDownloaderConfig, cookie_manager: CookieManager):
        """初始化路由器。
        
        Args:
            config: 下载器配置
            cookie_manager: Cookie管理器
        """
        self.downloader = TwitterDownloader(config, cookie_manager)
        
    def download(self, url: str) -> Dict[str, Any]:
        """根据URL类型选择下载方法。
        
        Args:
            url: 下载URL
            
        Returns:
            Dict[str, Any]: 下载结果信息
            
        Raises:
            DownloadError: 下载失败时抛出
        """
        # 检查URL类型
        if '/status/' in url:
            return self.downloader.download(url)
        else:
            return self.downloader.download_channel(url) 