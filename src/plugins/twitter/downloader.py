"""Twitter视频下载器模块。

该模块负责从Twitter下载视频和图片。
支持认证和代理功能。
"""

import os
import logging
import json
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import yt_dlp
from datetime import datetime
import time
from tqdm import tqdm
import re
import requests
from urllib.parse import urlparse

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError
from src.utils.cookie_manager import CookieManager
from .config import TwitterDownloaderConfig

logger = logging.getLogger(__name__)

class TwitterDownloader(BaseDownloader):
    """Twitter视频下载器。
    
    使用yt-dlp从Twitter下载视频和图片。
    支持认证和代理功能。
    
    Attributes:
        config: TwitterDownloaderConfig, 下载器配置
    """
    
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
            cookie_manager=cookie_manager
        )
        self.config = config
        self._setup_yt_dlp()

    def _setup_yt_dlp(self):
        """设置yt-dlp下载器。"""
        self.ydl_opts = {
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
                self.ydl_opts['cookiefile'] = cookie_file

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

    def download(self, url: str) -> Dict[str, Any]:
        """下载单个推文中的媒体。

        Args:
            url: 推文URL

        Returns:
            Dict[str, Any]: 下载结果
        """
        try:
            if not self._validate_url(url):
                raise DownloadError("不支持的URL格式")
                
            logger.info(f"开始下载推文: {url}")
            
            # 规范化URL
            url = self._normalize_url(url)
            
            # 首先尝试下载视频
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info and (info.get('formats') or info.get('entries')):
                        result = ydl.download([url])
                        if result == 0:
                            return {
                                'success': True,
                                'media_count': 1,
                                'url': url,
                                'info': info
                            }
            except Exception as e:
                logger.debug(f"视频下载失败，尝试下载图片: {str(e)}")
            
            # 如果视频下载失败，尝试下载图片
            result = self._try_download_image_from_html(url)
            if not result['success']:
                raise DownloadError(result.get('message', '下载失败'))
                
            return result
                    
        except Exception as e:
            logger.error(f"下载出错: {str(e)}")
            return {
                'success': False,
                'message': str(e),
                'url': url
            }

    def download_channel(self, url: str, max_count: Optional[int] = None) -> Dict[str, Any]:
        """下载用户频道的所有媒体。

        Args:
            url: 用户主页URL
            max_count: 最大下载数量

        Returns:
            Dict[str, Any]: 下载结果
        """
        try:
            if not self._validate_url(url):
                raise DownloadError("不支持的URL格式")
                
            # 检查是否为用户主页
            if '/status/' in url:
                raise DownloadError("该功能仅支持Twitter用户主页")
                
            logger.info(f"开始下载用户内容: {url}")
            
            # 规范化URL并添加media路径
            url = f"{self._normalize_url(url)}/media"
            
            # 修改配置以支持频道下载
            channel_opts = self.ydl_opts.copy()
            channel_opts.update({
                'extract_flat': False,
                'playlistreverse': True,
                'playlistend': max_count if max_count else None,
                'playlist_items': f'1:{max_count}' if max_count else None,
                'ignoreerrors': True,
                'extractor_args': {
                    'twitter': {
                        'api': ['graphql'],
                    }
                }
            })
            
            with yt_dlp.YoutubeDL(channel_opts) as ydl:
                try:
                    # 获取用户信息
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        raise DownloadError(f"无法获取用户信息: {url}")
                    
                    # 获取要下载的媒体列表
                    entries = info.get('entries', [])
                    if not entries:
                        raise DownloadError(f"未找到可下载的内容: {url}")
                        
                    # 限制下载数量
                    if max_count:
                        entries = entries[:max_count]
                    
                    # 下载所有媒体
                    failed = []
                    success_count = 0
                    
                    for entry in entries:
                        try:
                            video_url = entry.get('url') or entry.get('webpage_url')
                            if not video_url:
                                continue
                                
                            # 尝试下载
                            result = self.download(video_url)
                            if result['success']:
                                success_count += result.get('media_count', 1)
                            else:
                                failed.append(video_url)
                                
                        except Exception as e:
                            logger.error(f"下载媒体失败 {entry.get('url')}: {str(e)}")
                            failed.append(entry.get('url'))
                    
                    # 返回下载结果
                    return {
                        'success': True,
                        'media_count': success_count,
                        'failed_count': len(failed),
                        'failed_urls': failed,
                        'url': url,
                        'info': info
                    }
                    
                except Exception as e:
                    logger.error(f"下载用户内容失败 {url}: {str(e)}")
                    return {
                        'success': False,
                        'message': str(e),
                        'url': url
                    }
                    
        except Exception as e:
            logger.error(f"频道下载失败: {str(e)}")
            return {
                'success': False,
                'message': str(e),
                'url': url
            }

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