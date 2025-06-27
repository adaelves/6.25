"""Twitter视频下载器模块。

该模块负责从Twitter下载视频和图片。
支持认证和代理功能。
"""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import yt_dlp
from datetime import datetime, timezone
import time
import requests
import json

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
        
        # 如果配置中有cookies，保存到cookie管理器
        if config.cookies:
            self.cookie_manager.save_cookies("twitter", config.cookies)
        
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
            
        Notes:
            - 使用Netscape格式的Cookie文件
            - 添加必要的认证头部
            - 启用详细日志和错误报告
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
        options = {
            # Cookie认证
            'cookiefile': str(cookie_file),
            'http_headers': {
                # 基本头部
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'application/json',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                
                # Twitter特定头部
                'X-Twitter-Auth-Type': 'OAuth2Session',
                'X-Twitter-Client-Language': 'en',
                'X-Twitter-Active-User': 'yes',
                'Authorization': f'Bearer {cookies.get("auth_token", "")}',
                'x-csrf-token': cookies.get('ct0', ''),
                
                # 安全头部
                'Referer': 'https://twitter.com/',
                'Origin': 'https://twitter.com',
                'DNT': '1'
            },
            
            # Twitter API设置
            'extractor_args': {
                'twitter': {
                    'api': ['graphql'],
                }
            },
            
            # 认证设置
            'username': cookies.get('auth_token', ''),  # 使用auth_token作为用户名
            'password': cookies.get('ct0', ''),        # 使用ct0作为密码
            
            # 错误处理和日志
            'ignoreerrors': False,
            'verbose': True,
            
            # 下载设置
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': str(self.config.save_dir / '%(title)s.%(ext)s'),
            
            # 代理设置
            'proxy': self.config.proxy if self.config.proxy else None,
            
            # 重试设置
            'retries': 10,
            'retry_sleep': lambda n: 5 * (n + 1),
            
            # 调试设置
            'debug_printtraffic': True,
            'no_color': True,
            
            # 添加视频相关选项
            'format_sort': ['res:2160', 'res:1440', 'res:1080', 'res:720', 'res:480'],  # 按分辨率排序
            'video_multistreams': True,  # 启用多流支持
            'prefer_free_formats': False,  # 不限制格式
            'format_sort_force': True,  # 强制按指定顺序排序
        }
        
        logger.debug(f"下载选项: {options}")
        return options
        
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
                        photo_url = photo.get('url')
                        if photo_url:
                            photo_path = user_dir / f"{info['id']}_{i}.jpg"
                            # 使用yt-dlp下载图片
                            ydl.download([photo_url])
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
                
    def _extract_images(self, tweet_id: str, max_retries: int = 3) -> dict:
        """从新版API提取图片URL。
        
        Args:
            tweet_id: 推文ID
            max_retries: 最大重试次数
            
        Returns:
            dict: 包含图片URL列表和用户信息的字典
        """
        api_url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}"
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 构建请求头
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json,text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Referer': 'https://twitter.com/',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'cross-site',
                    'Pragma': 'no-cache',
                    'Cache-Control': 'no-cache'
                }
                
                # 添加代理配置
                proxies = {'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None
                
                # 发送请求
                response = requests.get(
                    api_url,
                    headers=headers,
                    proxies=proxies,
                    timeout=30
                )
                response.raise_for_status()
                
                # 记录响应内容以便调试
                logger.debug(f"API响应状态码: {response.status_code}")
                logger.debug(f"API响应头: {dict(response.headers)}")
                logger.debug(f"API响应内容: {response.text[:1000]}")  # 只记录前1000个字符
                
                # 尝试解析JSON
                try:
                    data = response.json()
                except ValueError as e:
                    logger.error(f"JSON解析失败: {e}")
                    logger.error(f"响应内容: {response.text}")
                    raise
                
                # 提取图片URL和用户信息
                images = []
                
                # 检查媒体详情
                media_details = data.get('mediaDetails', [])
                if media_details:
                    for media in media_details:
                        if media.get('type') == 'photo':
                            url = media.get('url', '')
                            if url:
                                # 添加参数获取最大尺寸
                                url = f"{url}?format=jpg&name=4096x4096"
                                images.append(url)
                else:
                    # 尝试从其他可能的字段提取
                    photos = data.get('photos', [])
                    if photos:
                        for photo in photos:
                            url = photo.get('url', '')
                            if url:
                                url = f"{url}?format=jpg&name=4096x4096"
                                images.append(url)
                
                # 如果还是没有找到图片，尝试其他可能的字段
                if not images:
                    media = data.get('media', [])
                    if media:
                        for item in media:
                            if item.get('type') == 'photo':
                                url = item.get('url', '')
                                if url:
                                    url = f"{url}?format=jpg&name=4096x4096"
                                    images.append(url)
                
                # 获取用户信息
                user = data.get('user', {}).get('screen_name', '')
                if not user:
                    # 尝试其他可能的用户信息字段
                    user = data.get('author_name', '') or data.get('screen_name', '')
                
                result = {
                    'images': images,
                    'user': user,
                    'tweet_id': tweet_id
                }
                
                logger.debug(f"提取结果: {result}")
                return result
                
            except requests.RequestException as e:
                logger.warning(f"第{retry_count + 1}次请求失败: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)  # 指数退避
                continue
            except Exception as e:
                logger.error(f"解析推文数据失败: {e}")
                logger.error(f"异常详情: {str(e)}")
                if hasattr(e, '__traceback__'):
                    import traceback
                    logger.error(f"堆栈跟踪: {traceback.format_exc()}")
                break
                
        logger.error(f"提取图片失败，已重试{retry_count}次")
        return {}

    def _extract_images_from_tweet_data(self, tweet_data: Dict) -> list:
        """从推文数据中提取图片URL。
        
        Args:
            tweet_data: 推文数据字典
            
        Returns:
            list: 图片URL列表
        """
        images = []
        try:
            # 检查扩展实体
            extended_entities = tweet_data.get('extended_entities', {})
            if extended_entities:
                media = extended_entities.get('media', [])
                for item in media:
                    if item.get('type') == 'photo':
                        url = item.get('media_url_https', '')
                        if url:
                            url = f"{url}?format=jpg&name=4096x4096"
                            images.append(url)
                            
            # 如果没有扩展实体，检查基本媒体
            if not images:
                media = tweet_data.get('entities', {}).get('media', [])
                for item in media:
                    if item.get('type') == 'photo':
                        url = item.get('media_url_https', '')
                        if url:
                            url = f"{url}?format=jpg&name=4096x4096"
                            images.append(url)
                            
            # 检查其他可能的图片字段
            if not images:
                photos = tweet_data.get('photos', [])
                for photo in photos:
                    url = photo.get('url', '')
                    if url:
                        url = f"{url}?format=jpg&name=4096x4096"
                        images.append(url)
                        
        except Exception as e:
            logger.error(f"提取图片URL失败: {e}")
            
        return images

    def _extract_images_fallback(self, tweet_id: str) -> dict:
        """使用GraphQL API提取图片URL（备用方法）。
        
        Args:
            tweet_id: 推文ID
            
        Returns:
            dict: 包含图片URL列表和用户信息的字典
        """
        api_url = "https://api.twitter.com/2/tweets"
        params = {
            "ids": tweet_id,
            "tweet.fields": "attachments,entities,extended_entities",
            "expansions": "attachments.media_keys",
            "media.fields": "url,preview_image_url,type"
        }
        
        try:
            headers = {
                'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'x-twitter-client-language': 'en',
                'x-twitter-active-user': 'yes',
                'Referer': 'https://twitter.com/',
                'Origin': 'https://twitter.com',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive'
            }
            
            # 添加Cookie相关的头部
            cookies = self.cookie_manager.get_cookies(self.platform)
            if cookies:
                headers['x-csrf-token'] = cookies.get('ct0', '')
                headers['Cookie'] = self.cookie_manager.to_header(self.platform)
            
            response = requests.get(
                api_url,
                params=params,
                headers=headers,
                proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                timeout=30
            )
            response.raise_for_status()
            
            # 记录完整的响应内容
            logger.debug(f"API请求URL: {response.url}")
            logger.debug(f"API请求头: {headers}")
            logger.debug(f"API响应状态码: {response.status_code}")
            logger.debug(f"API响应头: {dict(response.headers)}")
            logger.debug(f"API响应内容: {response.text}")
            
            data = response.json()
            
            # 提取图片URL和用户信息
            images = []
            user = ''
            
            # 检查推文数据
            tweets = data.get('data', [])
            if not tweets:
                logger.warning("未找到推文数据")
                return {}
            
            tweet = tweets[0] if isinstance(tweets, list) else tweets
            
            # 检查媒体附件
            media = data.get('includes', {}).get('media', [])
            for item in media:
                if item.get('type') == 'photo':
                    url = item.get('url', '')
                    if url:
                        url = f"{url}?format=jpg&name=4096x4096"
                        images.append(url)
            
            # 如果没有找到媒体，尝试从实体中提取
            if not images:
                entities = tweet.get('entities', {})
                if 'media' in entities:
                    for item in entities['media']:
                        if item.get('type') == 'photo':
                            url = item.get('media_url_https', '')
                            if url:
                                url = f"{url}?format=jpg&name=4096x4096"
                                images.append(url)
            
            # 如果还是没有找到，尝试从扩展实体中提取
            if not images:
                extended_entities = tweet.get('extended_entities', {})
                if 'media' in extended_entities:
                    for item in extended_entities['media']:
                        if item.get('type') == 'photo':
                            url = item.get('media_url_https', '')
                            if url:
                                url = f"{url}?format=jpg&name=4096x4096"
                                images.append(url)
            
            # 获取用户信息
            user = tweet.get('user', {}).get('screen_name', '') or tweet_id
            
            result = {
                'images': images,
                'user': user,
                'tweet_id': tweet_id
            }
            
            logger.debug(f"提取结果: {result}")
            return result
            
        except Exception as e:
            logger.error(f"API提取失败: {e}")
            logger.error(f"异常详情: {str(e)}")
            if hasattr(e, '__traceback__'):
                import traceback
                logger.error(f"堆栈跟踪: {traceback.format_exc()}")
            return {}

    def _extract_images_web(self, tweet_id: str) -> dict:
        """通过网页抓取方式提取图片URL。
        
        Args:
            tweet_id: 推文ID
            
        Returns:
            dict: 包含图片URL列表和用户信息的字典
        """
        url = f"https://twitter.com/i/status/{tweet_id}"
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://twitter.com/',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'TE': 'trailers'
            }
            
            # 添加Cookie
            cookies = self.cookie_manager.get_cookies(self.platform)
            if cookies:
                headers['Cookie'] = self.cookie_manager.to_header(self.platform)
            
            # 添加代理配置
            proxies = {'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None
            
            response = requests.get(
                url,
                headers=headers,
                proxies=proxies,
                timeout=30
            )
            response.raise_for_status()
            
            # 记录响应内容
            logger.debug(f"Web请求URL: {url}")
            logger.debug(f"Web请求头: {headers}")
            logger.debug(f"Web响应状态码: {response.status_code}")
            logger.debug(f"Web响应头: {dict(response.headers)}")
            
            # 在响应内容中查找图片URL
            content = response.text
            images = []
            
            # 查找所有可能的图片URL模式
            import re
            patterns = [
                r'https://pbs\.twimg\.com/media/[^"\']+',
                r'https://pbs\.twimg\.com/tweet_video_thumb/[^"\']+',
                r'https://pbs\.twimg\.com/ext_tw_video_thumb/[^"\']+',
                r'https://pbs\.twimg\.com/amplify_video_thumb/[^"\']+',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for url in matches:
                    # 清理URL并添加参数
                    url = url.split('?')[0]  # 移除现有参数
                    url = f"{url}?format=jpg&name=4096x4096"
                    if url not in images:
                        images.append(url)
            
            # 提取用户名
            user_pattern = r'twitter\.com/([^/"]+)/status/'
            user_match = re.search(user_pattern, response.url)
            user = user_match.group(1) if user_match else tweet_id
            
            result = {
                'images': images,
                'user': user,
                'tweet_id': tweet_id
            }
            
            logger.debug(f"Web抓取结果: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Web抓取失败: {e}")
            if hasattr(e, '__traceback__'):
                import traceback
                logger.error(f"堆栈跟踪: {traceback.format_exc()}")
            return {}

    def _download_file(self, url: str, save_path: Path, max_retries: int = 3) -> bool:
        """下载单个文件。
        
        Args:
            url: 文件URL
            save_path: 保存路径
            max_retries: 最大重试次数
            
        Returns:
            bool: 是否下载成功
        """
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = requests.get(
                    url,
                    headers=self.get_download_options().get('http_headers', {}),
                    proxies={'http': self.config.proxy, 'https': self.config.proxy} if self.config.proxy else None,
                    timeout=30,
                    stream=True  # 启用流式下载
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
                
            except requests.RequestException as e:
                logger.warning(f"第{retry_count + 1}次下载失败: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)  # 指数退避
                continue
            except Exception as e:
                logger.error(f"下载文件失败: {e}")
                break
                
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
            methods = [
                (self._extract_images, "Syndication API"),
                (self._extract_images_fallback, "Twitter API v2"),
                (self._extract_images_web, "Web抓取")
            ]
            
            data = {}
            for method, name in methods:
                logger.info(f"尝试使用{name}获取图片...")
                data = method(tweet_id)
                if data.get('images'):
                    logger.info(f"使用{name}成功获取到图片")
                    break
                logger.warning(f"{name}未返回图片，尝试下一个方法")
            
            if not data:
                logger.error("所有方法都失败，无法获取推文信息")
                return False
            
            images = data.get('images', [])
            username = data.get('user')
            
            if not images:
                logger.warning("未检测到可下载媒体")
                return False
                
            if not username:
                logger.warning("无法获取用户名，使用推文ID作为目录名")
                username = tweet_id
            
            # 创建保存目录
            user_dir = self.config.save_dir / username
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # 下载所有图片
            success = False
            for idx, img_url in enumerate(images, 1):
                save_path = user_dir / f"{tweet_id}_{idx}.jpg"
                
                logger.info(f"开始下载第{idx}张图片: {img_url}")
                if self._download_file(img_url, save_path):
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