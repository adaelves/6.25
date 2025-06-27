"""Twitter视频下载器模块。

该模块负责从Twitter下载视频和图片。
支持认证和代理功能。
"""

import os
import logging
from typing import Optional, Dict, Any, List, Set
from pathlib import Path
import yt_dlp
from datetime import datetime, timezone
import time
import requests
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError
from src.utils.cookie_manager import CookieManager
from .config import TwitterDownloaderConfig

logger = logging.getLogger(__name__)

class TwitterDownloader(BaseDownloader):
    """Twitter视频下载器。
    
    使用yt-dlp库从Twitter下载视频。
    支持认证和代理功能。
    
    Attributes:
        config: TwitterDownloaderConfig, 下载器配置
    """
    
    def __init__(
        self,
        config: TwitterDownloaderConfig,
        cookie_manager: Optional[CookieManager] = None
    ):
        """初始化下载器。
        
        Args:
            config: 下载器配置
            cookie_manager: Cookie管理器，如果不提供则创建新实例
        """
        super().__init__(
            platform="twitter",
            save_dir=config.save_dir,
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cookie_manager=cookie_manager
        )
        self.config = config
        self.downloaded_path = Path("config/downloaded.json")
        self.downloaded_ids = self._load_downloaded_ids()
        self.proxies = self._load_proxies()
        self.current_proxy_index = 0
        self.rate_limit_delay = (2, 5)  # 请求延迟范围（秒）
        self.rate_limit_wait = 30  # 触发限流后等待时间（秒）
        
        # 如果配置中有cookies，保存到cookie管理器
        if config.cookies:
            self.cookie_manager.save_cookies("twitter", config.cookies)
        
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
            
    def _get_webdriver(self) -> webdriver.Chrome:
        """获取配置好的Chrome WebDriver。
        
        Returns:
            webdriver.Chrome: 配置好的WebDriver实例
        """
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # 无头模式
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-software-rasterizer')  # 禁用软件光栅化器
        options.add_argument('--disable-extensions')  # 禁用扩展
        options.add_argument('--disable-logging')  # 禁用日志
        options.add_argument('--log-level=3')  # 只显示致命错误
        options.add_argument(f'user-agent={self._get_random_user_agent()}')
        
        if self.config.proxy:
            options.add_argument(f'--proxy-server={self.config.proxy}')
            
        # 创建driver
        driver = webdriver.Chrome(options=options)
        
        # 设置Cookie
        cookies = self.cookie_manager.get_cookies(self.platform)
        if cookies:
            # 先访问twitter.com域名
            driver.get('https://twitter.com')
            time.sleep(2)  # 等待页面加载
            
            # 添加Cookie
            for name, value in cookies.items():
                try:
                    cookie = {
                        'name': name,
                        'value': value,
                        'domain': '.twitter.com',  # 使用.twitter.com作为域名
                        'path': '/'
                    }
                    driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(f"添加Cookie失败 {name}: {e}")
                    
            # 刷新页面以应用Cookie
            driver.refresh()
            time.sleep(2)  # 等待刷新完成
                
        return driver
        
    def _scrape_tweets(self, profile_url: str, max_tweets: int = 100) -> List[str]:
        """爬取用户推文链接。
        
        Args:
            profile_url: 用户主页URL
            max_tweets: 最大爬取推文数
            
        Returns:
            List[str]: 推文URL列表
        """
        logger.info(f"开始爬取用户推文: {profile_url}")
        tweet_urls = []
        retry_count = 0
        
        while retry_count < self.config.max_retries:
            driver = None
            try:
                driver = self._get_webdriver()
                
                # 统一使用twitter.com域名
                if "x.com" in profile_url:
                    profile_url = profile_url.replace("x.com", "twitter.com")
                
                # 访问用户主页
                driver.get(profile_url)
                time.sleep(3)  # 等待页面加载
                
                # 等待推文加载
                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'article'))
                    )
                except TimeoutException:
                    logger.warning("等待推文加载超时，尝试继续处理")
                
                last_height = driver.execute_script("return document.body.scrollHeight")
                tweet_count = 0
                no_new_tweets_count = 0
                scroll_pause_time = 2
                
                while tweet_count < max_tweets and no_new_tweets_count < 3:
                    # 解析当前页面推文
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    articles = soup.find_all('article')
                    
                    initial_count = len(tweet_urls)
                    for article in articles:
                        # 查找推文链接
                        link = article.find('a', href=re.compile(r'/status/\d+'))
                        if link and 'href' in link.attrs:
                            tweet_url = f"https://twitter.com{link['href']}"
                            tweet_id = link['href'].split('/status/')[-1]
                            
                            # 检查是否已下载
                            if tweet_id not in self.downloaded_ids and tweet_url not in tweet_urls:
                                tweet_urls.append(tweet_url)
                                tweet_count += 1
                                logger.debug(f"找到推文: {tweet_url}")
                                
                            if tweet_count >= max_tweets:
                                break
                    
                    # 检查是否有新推文
                    if len(tweet_urls) == initial_count:
                        no_new_tweets_count += 1
                        logger.debug(f"未发现新推文，计数: {no_new_tweets_count}")
                    else:
                        no_new_tweets_count = 0
                    
                    # 随机延迟
                    self._random_delay()
                    
                    # 滚动到底部
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(scroll_pause_time)
                    
                    # 检查是否到达底部
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        logger.debug("已到达页面底部")
                        break
                    last_height = new_height
                
                break  # 成功获取推文，退出重试循环
                
            except Exception as e:
                retry_count += 1
                logger.error(f"爬取推文失败: {e}")
                if retry_count < self.config.max_retries:
                    wait_time = 2 ** retry_count
                    logger.info(f"等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                    
        logger.info(f"找到{len(tweet_urls)}条未下载推文")
        return tweet_urls
        
    def download_with_retry(self, url: str) -> bool:
        """带重试和延迟的下载单条推文。
        
        Args:
            url: 推文URL
            
        Returns:
            bool: 是否下载成功
        """
        tweet_id = url.split('/status/')[-1].split('?')[0]
        retry_count = 0
        max_retries = self.config.max_retries
        
        while retry_count < max_retries:
            try:
                if tweet_id in self.downloaded_ids:
                    logger.info(f"推文已下载，跳过: {url}")
                    return True
                
                # 随机延迟
                self._random_delay()
                
                if self.download(url):
                    self.downloaded_ids.add(tweet_id)
                    self._save_downloaded_ids()
                    return True
                    
            except yt_dlp.DownloadError as e:
                error_msg = str(e).lower()
                if '429' in error_msg or 'too many requests' in error_msg:
                    self._handle_rate_limit(retry_count)
                    retry_count += 1
                    continue
                else:
                    logger.error(f"下载失败: {url} - {e}")
                    return False
                    
            except Exception as e:
                logger.error(f"下载推文失败: {url} - {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)  # 指数退避
                continue
                
        logger.error(f"下载失败，已重试{retry_count}次: {url}")
        return False
            
    def download_channel(self, profile_url: str, max_tweets: int = 100, max_workers: int = 3) -> None:
        """下载用户所有媒体内容。
        
        Args:
            profile_url: 用户主页URL
            max_tweets: 最大下载推文数
            max_workers: 最大并发下载数
        """
        logger.info(f"开始下载用户媒体: {profile_url}")
        
        # 获取所有推文链接
        tweet_urls = self._scrape_tweets(profile_url, max_tweets)
        if not tweet_urls:
            logger.warning("未找到需要下载的推文")
            return
            
        # 并发下载
        success_count = 0
        failed_urls = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(self.download_with_retry, url): url 
                for url in tweet_urls
            }
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    if future.result():
                        success_count += 1
                    else:
                        failed_urls.append(url)
                except Exception as e:
                    logger.error(f"下载失败: {url} - {e}")
                    failed_urls.append(url)
                    
        # 输出统计信息
        logger.info(f"下载完成: 成功{success_count}条, 失败{len(failed_urls)}条")
        if failed_urls:
            logger.info("失败列表:")
            for url in failed_urls:
                logger.info(f"  {url}")

    def _save_cookies_netscape(self, cookies: Dict[str, str], cookie_file: Path) -> None:
        """将Cookie保存为Netscape格式。
        
        Args:
            cookies: Cookie字典
            cookie_file: 保存路径
            
        Notes:
            Netscape格式:
            domain\tHTTP_ONLY\tpath\tSECURE\texpiry\tname\tvalue
        """
        # 确保目录存在
        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 设置默认值
        domains = [".twitter.com", ".x.com"]  # 支持两个域名
        default_path = "/"
        # 设置过期时间为1年后
        expiry = int(time.time()) + 365 * 24 * 60 * 60
        
        try:
            with open(cookie_file, 'w', encoding='utf-8') as f:
                # 写入文件头
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n")
                f.write("# This is a generated file!  Do not edit.\n\n")
                
                # 写入每个Cookie到两个域名
                for domain in domains:
                    for name, value in cookies.items():
                        # domain HTTP_ONLY path SECURE expiry name value
                        line = f"{domain}\tTRUE\t{default_path}\tTRUE\t{expiry}\t{name}\t{value}\n"
                        f.write(line)
                    
            logger.info(f"Cookie已保存到Netscape格式文件: {cookie_file}")
            
        except Exception as e:
            logger.error(f"保存Netscape格式Cookie失败: {e}")
            raise
        
    def _progress_hook(self, d: Dict[str, Any]) -> None:
        """下载进度回调。
        
        Args:
            d: 进度信息字典
        """
        if d['status'] == 'downloading':
            # 计算进度
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            
            if total > 0 and downloaded is not None:
                progress = downloaded / total
                speed_text = f"{speed/1024:.1f} KB/s" if speed else "Unknown"
                eta_text = f"{eta}s" if eta else "Unknown"
                
                # 区分视频和图片的进度
                media_type = "视频" if d.get('video_ext') else "图片"
                self.update_progress(
                    progress,
                    f"{media_type}下载进度: {downloaded}/{total} bytes"
                    f" ({speed_text}, ETA: {eta_text})"
                )
                
    def _post_process_hook(self, d: Dict[str, Any]) -> None:
        """后处理回调。
        
        Args:
            d: 处理信息字典
        """
        status = d.get('status')
        if status == 'finished':
            filename = d.get('filename', '')
            if filename:
                media_type = "视频" if filename.endswith('.mp4') else "图片"
                logger.info(f"{media_type}下载完成: {filename}")
                
    def get_download_options(self) -> Dict[str, Any]:
        """获取下载选项。
        
        Returns:
            Dict[str, Any]: 下载选项字典
        """
        # 检查Cookie状态
        cookies = self.cookie_manager.get_cookies("twitter")
        if not cookies:
            logger.error("未找到Twitter Cookie")
            raise ValueError("请先完成Twitter认证")
            
        # 检查必需的Cookie
        required_cookies = {"auth_token", "ct0"}
        missing_cookies = required_cookies - set(cookies.keys())
        if missing_cookies:
            logger.error(f"缺少必需的Cookie: {missing_cookies}")
            raise ValueError("Twitter认证信息不完整")
            
        # 保存为Netscape格式
        cookie_dir = Path("config/cookies")
        cookie_file = cookie_dir / "twitter.txt"  # 使用.txt扩展名
        self._save_cookies_netscape(cookies, cookie_file)
            
        # 构建下载选项
        return {
            'cookiefile': str(cookie_file),
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Referer': 'https://twitter.com/',
                'X-Forwarded-For': f'127.0.0.{random.randint(1, 255)}'
            },
            'extract_flat': True,
            'force_generic_extractor': True,
            'extract_flat_videos': True,
            
            # 代理设置
            'proxy': self.config.proxy if self.config.proxy else None,
            
            # 重试设置
            'retries': self.config.max_retries,
            'retry_sleep': lambda n: 5 * (n + 1),
            
            # 调试设置
            'verbose': True,
            'debug_printtraffic': True,
            'no_color': True,
            
            # 下载设置
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': str(self.config.save_dir / '%(title)s.%(ext)s'),
            
            # 其他设置
            'ignoreerrors': False,
            'no_warnings': False,
            'progress_hooks': [self._progress_hook],
            'postprocessor_hooks': [self._post_process_hook]
        }
        
    def download(self, url: str) -> bool:
        """下载视频或图片。
        
        Args:
            url: 推文URL
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            ValueError: Cookie无效或不完整
            Exception: 下载过程中的其他错误
        """
        try:
            logger.info(f"开始下载Twitter内容: {url}")
            
            # 获取基本下载选项
            options = self.get_download_options()
            
            # 先获取推文信息以确定用户名
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                username = info.get('uploader', 'unknown')
                
            # 创建用户专属目录
            user_dir = self.config.save_dir / username
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # 添加图片和视频下载相关选项
            media_options = {
                'extract_flat': True,  # 扁平化提取
                'extract_images': True,  # 启用图片提取
                'writethumbnail': True,  # 下载缩略图
                'paths': {
                    'home': str(user_dir)  # 用户专属目录
                },
                'outtmpl': {
                    'default': '%(id)s.%(ext)s',  # 视频模板
                    'image': '%(id)s_%(autonumber)d.%(ext)s',  # 图片模板
                    'thumbnail': '%(id)s_thumb.%(ext)s'  # 缩略图模板
                },
                'progress_hooks': [self._progress_hook],  # 进度回调
                'postprocessor_hooks': [self._post_process_hook],  # 后处理回调
                
                # 图片下载器设置
                'postprocessors': [{
                    'key': 'FFmpegMetadata',  # 保留元数据
                }, {
                    'key': 'ModifyChapters',  # 处理章节信息
                    'remove_chapters_patterns': ['.*?']  # 移除所有章节
                }],
                
                # 强制下载所有媒体
                'download_archive': None,  # 禁用下载历史
                'break_on_reject': False,  # 遇到错误继续
                'ignore_no_formats_error': True,  # 忽略格式错误
                'extract_flat': False  # 禁用扁平化提取以获取完整信息
            }
            
            # 合并选项
            options.update(media_options)
            
            # 执行下载
            with yt_dlp.YoutubeDL(options) as ydl:
                logger.debug(f"使用选项下载: {options}")
                info = ydl.extract_info(url, download=True)
                
                # 记录下载结果
                entries = info.get('entries', [info]) if info.get('_type') == 'playlist' else [info]
                video_count = len([e for e in entries if e.get('_type') == 'video'])
                image_count = len([e for e in entries if e.get('_type') == 'image'])
                
                # 如果没有找到视频或图片，尝试从推文信息中提取图片URL
                if video_count == 0 and image_count == 0 and 'photos' in info:
                    photos = info.get('photos', [])
                    for i, photo in enumerate(photos, 1):
                        photo_url = user_dir / f"{info['id']}_{i}.jpg"
                        # 使用yt-dlp下载图片
                        ydl.download([photo.get('url')])
                        image_count += 1
                
                logger.info(
                    f"下载完成到目录 {user_dir}: "
                    f"{video_count}个视频, "
                    f"{image_count}张图片"
                )
                
            return True
            
        except ValueError as e:
            logger.error(f"Twitter认证错误: {e}")
            raise
            
        except Exception as e:
            if "No video could be found in this tweet" in str(e):
                # 如果是纯图片推文，尝试重新下载
                logger.info("推文不包含视频，尝试下载图片...")
                try:
                    return self._download_images_only(url)
                except Exception as img_e:
                    logger.error(f"图片下载失败: {img_e}")
                    raise
            else:
                logger.error(f"Twitter内容下载出错: {e}")
                raise
                
    def _get_random_user_agent(self) -> str:
        """获取随机User-Agent。
        
        Returns:
            str: 随机选择的User-Agent字符串
        """
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        return random.choice(user_agents)

    def _extract_images_from_html(self, tweet_url: str) -> list:
        """从推文HTML页面提取图片URL。
        
        Args:
            tweet_url: 推文URL
            
        Returns:
            list: 图片URL列表
        """
        # 构建请求头
        headers = {
            'User-Agent': self._get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'DNT': '1',
            'Referer': 'https://twitter.com/',
            'X-Forwarded-For': f'127.0.0.{random.randint(1, 255)}'
        }
        
        # 添加认证信息
        cookies = self.cookie_manager.get_cookies(self.platform)
        if cookies:
            auth_token = cookies.get('auth_token', '')
            ct0 = cookies.get('ct0', '')
            headers.update({
                'Authorization': f'Bearer {auth_token}',
                'x-csrf-token': ct0,
                'Cookie': f'auth_token={auth_token}; ct0={ct0}'
            })
        
        try:
            # 先尝试使用x.com域名
            response = requests.get(
                tweet_url,
                headers=headers,
                proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                timeout=30
            )
            
            # 如果失败，尝试使用twitter.com域名
            if not response.ok:
                tweet_url = tweet_url.replace('x.com', 'twitter.com')
                response = requests.get(
                    tweet_url,
                    headers=headers,
                    proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                    timeout=30
                )
            
            response.raise_for_status()
            html = response.text
            
            logger.debug(f"HTML响应内容: {html[:1000]}")  # 记录前1000个字符用于调试
            
            images = set()
            
            # 1. 查找data-image-url属性
            if 'data-image-url="' in html:
                images.update(re.findall(r'data-image-url="([^"]+)"', html))
            
            # 2. 查找og:image元标签
            og_images = re.findall(r'<meta property="og:image" content="([^"]+)"', html)
            images.update(og_images)
            
            # 3. 查找所有可能的图片URL模式
            patterns = [
                r'https://pbs\.twimg\.com/media/[A-Za-z0-9_-]+\.(jpg|png|webp)',
                r'https://pbs\.twimg\.com/tweet_video_thumb/[A-Za-z0-9_-]+\.(jpg|png|webp)',
                r'https://pbs\.twimg\.com/ext_tw_video_thumb/[A-Za-z0-9_-]+/[^"\']+',
                r'https://pbs\.twimg\.com/amplify_video_thumb/[A-Za-z0-9_-]+/[^"\']+',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    if isinstance(match, tuple):
                        url = match[0]  # 获取URL部分
                    else:
                        url = match
                    # 清理URL并添加参数
                    url = url.split('?')[0]  # 移除现有参数
                    url = f"{url}?format=jpg&name=4096x4096"
                    images.add(url)
            
            # 4. 查找新的图片格式
            new_patterns = [
                r'"url":"(https://pbs\.twimg\.com/[^"]+)"',
                r'"image_url":"(https://pbs\.twimg\.com/[^"]+)"',
                r'"media_url_https":"(https://pbs\.twimg\.com/[^"]+)"'
            ]
            
            for pattern in new_patterns:
                matches = re.findall(pattern, html)
                for url in matches:
                    url = url.replace('\\', '')  # 移除JSON转义
                    url = url.split('?')[0]  # 移除现有参数
                    url = f"{url}?format=jpg&name=4096x4096"
                    images.add(url)
            
            return list(images)
            
        except Exception as e:
            logger.error(f"HTML解析提取图片失败: {e}")
            return []

    def _extract_images_from_api(self, tweet_id: str) -> list:
        """从Twitter API提取图片URL。
        
        Args:
            tweet_id: 推文ID
            
        Returns:
            list: 图片URL列表
        """
        api_url = f"https://api.twitter.com/2/tweets/{tweet_id}"
        
        # 获取认证信息
        cookies = self.cookie_manager.get_cookies(self.platform)
        if not cookies:
            logger.error("未找到Twitter Cookie")
            return []
            
        auth_token = cookies.get('auth_token', '')
        ct0 = cookies.get('ct0', '')
        
        headers = {
            'User-Agent': self._get_random_user_agent(),
            'Authorization': f'Bearer {auth_token}',
            'x-csrf-token': ct0,
            'Cookie': f'auth_token={auth_token}; ct0={ct0}',
            'x-twitter-client-language': 'en',
            'x-twitter-active-user': 'yes',
            'Referer': 'https://twitter.com/',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
        
        params = {
            'tweet.fields': 'attachments,entities',
            'expansions': 'attachments.media_keys',
            'media.fields': 'url,preview_image_url'
        }
        
        try:
            response = requests.get(
                api_url,
                headers=headers,
                params=params,
                proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            images = []
            
            # 从响应中提取图片URL
            media = data.get('includes', {}).get('media', [])
            for item in media:
                url = item.get('url') or item.get('preview_image_url')
                if url:
                    url = f"{url}?format=jpg&name=4096x4096"
                    images.append(url)
            
            return images
            
        except Exception as e:
            logger.error(f"API提取图片失败: {e}")
            return []

    def _extract_images_from_cdn(self, tweet_id: str) -> list:
        """从CDN获取图片URL。
        
        Args:
            tweet_id: 推文ID
            
        Returns:
            list: 图片URL列表
        """
        headers = {
            'User-Agent': self._get_random_user_agent(),
            'Accept': 'image/webp,*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://twitter.com/',
            'Connection': 'keep-alive'
        }
        
        try:
            # 构建可能的CDN URL模式
            cdn_patterns = [
                f"https://pbs.twimg.com/media/{tweet_id}?format=jpg&name=4096x4096",
                f"https://pbs.twimg.com/media/{tweet_id}.jpg?format=jpg&name=4096x4096",
                f"https://pbs.twimg.com/tweet_video_thumb/{tweet_id}.jpg",
                f"https://pbs.twimg.com/ext_tw_video_thumb/{tweet_id}/pu/img/large.jpg",
                f"https://pbs.twimg.com/amplify_video_thumb/{tweet_id}/img/large.jpg"
            ]
            
            valid_urls = []
            for url in cdn_patterns:
                try:
                    response = requests.head(
                        url,
                        headers=headers,
                        proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                        timeout=10
                    )
                    if response.status_code == 200:
                        valid_urls.append(url)
                except:
                    continue
                    
            return valid_urls
            
        except Exception as e:
            logger.error(f"CDN提取图片失败: {e}")
            return []

    def _download_file_with_retry(self, url: str, save_path: Path, max_retries: int = 3) -> bool:
        """使用智能重试机制下载文件。
        
        Args:
            url: 文件URL
            save_path: 保存路径
            max_retries: 最大重试次数
            
        Returns:
            bool: 是否下载成功
        """
        headers = {
            'User-Agent': self._get_random_user_agent(),
            'Referer': 'https://twitter.com/',
            'Accept': 'image/webp,*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'X-Forwarded-For': f'127.0.0.{random.randint(1, 255)}'
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                    timeout=30,
                    stream=True
                )
                response.raise_for_status()
                
                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                
                # 创建保存目录
                save_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 下载文件
                with open(save_path, 'wb') as f:
                    if total_size == 0:
                        f.write(response.content)
                    else:
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                # 更新进度
                                if self.progress_callback and total_size:
                                    progress = downloaded / total_size
                                    self.progress_callback(progress, f"下载进度: {downloaded}/{total_size} bytes")
                
                logger.info(f"文件已保存到: {save_path}")
                return True
                
            except Exception as e:
                wait_time = min(2 ** attempt, 60)  # 最大等待60秒
                logger.warning(f"第{attempt + 1}次下载失败 ({wait_time}秒后重试): {e}")
                if attempt < max_retries - 1:  # 如果不是最后一次尝试
                    time.sleep(wait_time)
                continue
                
        logger.error(f"下载失败，已重试{max_retries}次")
        return False

    def _download_images_only(self, url: str) -> bool:
        """专门处理纯图片推文的下载。
        
        Args:
            url: 推文URL
            
        Returns:
            bool: 是否下载成功
        """
        try:
            # 从URL中提取推文ID
            tweet_id = url.split('/status/')[-1].split('?')[0]
            logger.debug(f"提取到推文ID: {tweet_id}")
            
            # 尝试所有可能的方法获取图片
            images = []
            
            # 1. 首先尝试从HTML提取
            logger.info("尝试从HTML提取图片...")
            images = self._extract_images_from_html(url)
            
            # 2. 如果HTML提取失败，尝试CDN
            if not images:
                logger.info("HTML提取失败，尝试从CDN获取...")
                images = self._extract_images_from_cdn(tweet_id)
            
            # 3. 如果还是失败，尝试API
            if not images:
                logger.info("CDN获取失败，尝试使用API...")
                images = self._extract_images_from_api(tweet_id)
            
            if not images:
                logger.warning("未检测到可下载媒体")
                return False
            
            # 提取用户名
            username = None
            user_match = re.search(r'twitter\.com/([^/"]+)/status/', url)
            if user_match:
                username = user_match.group(1)
            if not username:
                username = tweet_id
            
            # 创建保存目录
            user_dir = self.config.save_dir / username
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # 下载所有图片
            success = False
            for idx, img_url in enumerate(images, 1):
                save_path = user_dir / f"{tweet_id}_{idx}.jpg"
                
                logger.info(f"开始下载第{idx}张图片: {img_url}")
                if self._download_file_with_retry(img_url, save_path):
                    success = True
                
            if success:
                logger.info(f"图片下载完成，保存到目录: {user_dir}")
                return True
            else:
                logger.error("所有图片下载失败")
                return False
                
        except Exception as e:
            logger.error(f"图片下载过程出错: {e}")
            raise

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息。
        
        Args:
            url: 视频URL
            
        Returns:
            Dict[str, Any]: 视频信息
            
        Raises:
            ValueError: URL无效
            DownloadError: 获取信息失败
        """
        try:
            ydl_opts = self.get_download_options()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
                
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            raise DownloadError(f"无法提取视频信息: {e}")

    def _load_proxies(self) -> List[str]:
        """加载代理列表。
        
        Returns:
            List[str]: 代理地址列表
        """
        try:
            proxy_path = Path("config/proxies.json")
            if proxy_path.exists():
                with open(proxy_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return [p.get('url') or p.get('proxy') or p for p in data]
            return []
        except Exception as e:
            logger.error(f"加载代理列表失败: {e}")
            return []

    def _get_next_proxy(self) -> Optional[str]:
        """获取下一个代理地址。
        
        Returns:
            Optional[str]: 代理地址或None
        """
        if not self.proxies:
            return self.config.proxy  # 如果没有代理列表，使用配置中的代理
            
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return proxy

    def _handle_rate_limit(self, retry_count: int) -> None:
        """处理限流情况。
        
        Args:
            retry_count: 当前重试次数
        """
        wait_time = min(self.rate_limit_wait * (2 ** retry_count), 300)  # 最多等待5分钟
        logger.warning(f"触发限流，等待{wait_time}秒...")
        time.sleep(wait_time)
        
        # 切换代理
        if self.proxies:
            new_proxy = self._get_next_proxy()
            logger.info(f"切换到新代理: {new_proxy}")
            self.config.proxy = new_proxy

    def _random_delay(self) -> None:
        """随机延迟请求。"""
        delay = random.uniform(*self.rate_limit_delay)
        time.sleep(delay)

    def download_with_retry(self, url: str) -> bool:
        """带重试和延迟的下载单条推文。
        
        Args:
            url: 推文URL
            
        Returns:
            bool: 是否下载成功
        """
        tweet_id = url.split('/status/')[-1].split('?')[0]
        retry_count = 0
        max_retries = self.config.max_retries
        
        while retry_count < max_retries:
            try:
                if tweet_id in self.downloaded_ids:
                    logger.info(f"推文已下载，跳过: {url}")
                    return True
                
                # 随机延迟
                self._random_delay()
                
                if self.download(url):
                    self.downloaded_ids.add(tweet_id)
                    self._save_downloaded_ids()
                    return True
                    
            except yt_dlp.DownloadError as e:
                error_msg = str(e).lower()
                if '429' in error_msg or 'too many requests' in error_msg:
                    self._handle_rate_limit(retry_count)
                    retry_count += 1
                    continue
                else:
                    logger.error(f"下载失败: {url} - {e}")
                    return False
                    
            except Exception as e:
                logger.error(f"下载推文失败: {url} - {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)  # 指数退避
                continue
                
        logger.error(f"下载失败，已重试{retry_count}次: {url}")
        return False

    def download_channel(self, profile_url: str, max_tweets: int = 100, max_workers: int = 3) -> None:
        """下载用户所有媒体内容。
        
        Args:
            profile_url: 用户主页URL
            max_tweets: 最大下载推文数
            max_workers: 最大并发下载数
        """
        logger.info(f"开始下载用户媒体: {profile_url}")
        
        # 获取所有推文链接
        tweet_urls = self._scrape_tweets(profile_url, max_tweets)
        if not tweet_urls:
            logger.warning("未找到需要下载的推文")
            return
            
        # 并发下载
        success_count = 0
        failed_urls = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(self.download_with_retry, url): url 
                for url in tweet_urls
            }
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    if future.result():
                        success_count += 1
                    else:
                        failed_urls.append(url)
                except Exception as e:
                    logger.error(f"下载失败: {url} - {e}")
                    failed_urls.append(url)
                    
        # 输出统计信息
        logger.info(f"下载完成: 成功{success_count}条, 失败{len(failed_urls)}条")
        if failed_urls:
            logger.info("失败列表:")
            for url in failed_urls:
                logger.info(f"  {url}") 