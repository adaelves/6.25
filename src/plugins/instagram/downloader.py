"""Instagram下载器模块。

提供Instagram视频、图片、故事等内容的下载功能。
"""

import os
import re
import json
import logging
from typing import Optional, Dict, Any, List, Generator
from pathlib import Path
import asyncio
from datetime import datetime
import time

import requests
from bs4 import BeautifulSoup
import yt_dlp

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError
from src.utils.cookie_manager import CookieManager
from src.extractors.instagram_extractor import InstagramExtractor
from .config import InstagramDownloaderConfig

logger = logging.getLogger(__name__)

class InstagramDownloader(BaseDownloader):
    """Instagram下载器。
    
    支持以下功能：
    - 视频下载
    - 图片下载
    - 故事下载
    - Reel下载
    - 相册下载
    - 精选故事下载
    - IGTV下载
    - 用户头像下载
    - 元数据提取
    
    Attributes:
        config: InstagramDownloaderConfig, 下载器配置
        extractor: InstagramExtractor, 内容提取器
    """
    
    # URL正则表达式
    VALID_URL_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?instagram\.com"
        r"/(?:p|reel|tv|stories)/[^/]+|"
        r"@[^/]+/(?:highlights|tagged)|"
        r"stories/highlights/\d+"
    )
    
    def __init__(
        self,
        config: InstagramDownloaderConfig,
        progress_callback: Optional[callable] = None,
        cookie_manager: Optional[CookieManager] = None
    ):
        """初始化下载器。
        
        Args:
            config: 下载器配置
            progress_callback: 进度回调函数
            cookie_manager: Cookie管理器
        """
        super().__init__(
            platform="instagram",
            save_dir=config.save_dir,
            progress_callback=progress_callback,
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cookie_manager=cookie_manager,
            config=config
        )
        
        self.config = config
        
        # 创建提取器
        self.extractor = InstagramExtractor(
            session=self.session,
            video_processor=None,  # TODO: 添加视频处理器
            metadata_cleaner=None  # TODO: 添加元数据清理器
        )
        
        # 设置yt-dlp
        self._setup_yt_dlp()
        
    def _setup_yt_dlp(self):
        """设置yt-dlp下载器。"""
        self.yt_dlp_opts = {
            # 基本配置
            'format': 'best',
            'outtmpl': os.path.join(
                str(self.save_dir),
                self.config.filename_template
            ),
            
            # 网络设置
            'proxy': self.proxy,
            'socket_timeout': self.timeout,
            'retries': self.max_retries,
            
            # 下载设置
            'ignoreerrors': True,
            'no_warnings': True,
            'quiet': True,
            
            # 回调函数
            'progress_hooks': [self._progress_hook],
            'postprocessor_hooks': [self._postprocessor_hook],
            
            # 元数据
            'writeinfojson': True,
            'writethumbnail': True,
            
            # 格式处理
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }]
        }
        
        # 添加Cookie支持
        if self.cookie_manager:
            cookie_file = self.cookie_manager.get_cookie_file("instagram")
            if os.path.exists(cookie_file):
                self.yt_dlp_opts['cookiefile'] = cookie_file
                
    def _validate_url(self, url: str) -> bool:
        """验证URL是否为有效的Instagram链接。
        
        Args:
            url: 要验证的URL
            
        Returns:
            bool: URL是否有效
        """
        return bool(self.VALID_URL_PATTERN.match(url))
        
    def _extract_media_info(self, url: str) -> Dict[str, Any]:
        """提取媒体信息。
        
        Args:
            url: 媒体URL
            
        Returns:
            Dict[str, Any]: 媒体信息
            
        Raises:
            DownloadError: 提取失败
        """
        try:
            # 获取页面内容
            response = self.session.get(
                url,
                headers={
                    **self.config.headers,
                    'User-Agent': self.config.user_agent
                }
            )
            response.raise_for_status()
            
            # 解析页面
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取共享数据
            shared_data = None
            for script in soup.find_all('script'):
                if script.string and 'window._sharedData' in script.string:
                    shared_data = json.loads(
                        script.string.split(' = ')[1].rstrip(';')
                    )
                    break
                    
            if not shared_data:
                raise DownloadError("无法提取媒体信息")
                
            # 提取媒体数据
            media_info = {}
            try:
                entry_data = shared_data['entry_data']
                if 'PostPage' in entry_data:
                    media_info = entry_data['PostPage'][0]['graphql']['shortcode_media']
                elif 'StoriesPage' in entry_data:
                    media_info = entry_data['StoriesPage'][0]['story']
            except (KeyError, IndexError) as e:
                raise DownloadError(f"解析媒体信息失败: {e}")
                
            return media_info
            
        except requests.RequestException as e:
            raise DownloadError(f"获取页面失败: {e}")
        except Exception as e:
            raise DownloadError(f"提取媒体信息失败: {e}")
            
    def _extract_media_urls(self, media_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取媒体URL。
        
        Args:
            media_info: 媒体信息
            
        Returns:
            List[Dict[str, Any]]: 媒体URL列表
        """
        media_urls = []
        
        try:
            # 处理视频
            if media_info.get('is_video'):
                media_urls.append({
                    'type': 'video',
                    'url': media_info['video_url'],
                    'thumbnail': media_info.get('display_url'),
                    'duration': media_info.get('video_duration'),
                    'view_count': media_info.get('video_view_count')
                })
                
            # 处理图片
            elif 'display_url' in media_info:
                media_urls.append({
                    'type': 'image',
                    'url': media_info['display_url'],
                    'width': media_info.get('dimensions', {}).get('width'),
                    'height': media_info.get('dimensions', {}).get('height')
                })
                
            # 处理相册
            if 'edge_sidecar_to_children' in media_info:
                for edge in media_info['edge_sidecar_to_children']['edges']:
                    node = edge['node']
                    if node.get('is_video'):
                        media_urls.append({
                            'type': 'video',
                            'url': node['video_url'],
                            'thumbnail': node.get('display_url'),
                            'duration': node.get('video_duration')
                        })
                    else:
                        media_urls.append({
                            'type': 'image',
                            'url': node['display_url'],
                            'width': node.get('dimensions', {}).get('width'),
                            'height': node.get('dimensions', {}).get('height')
                        })
                        
        except Exception as e:
            logger.error(f"提取媒体URL失败: {e}")
            
        return media_urls
        
    def _extract_metadata(self, media_info: Dict[str, Any]) -> Dict[str, Any]:
        """提取元数据。
        
        Args:
            media_info: 媒体信息
            
        Returns:
            Dict[str, Any]: 元数据
        """
        metadata = {
            'id': media_info.get('id'),
            'shortcode': media_info.get('shortcode'),
            'title': '',
            'description': '',
            'type': 'video' if media_info.get('is_video') else 'image',
            'timestamp': media_info.get('taken_at_timestamp'),
            'like_count': media_info.get('edge_media_preview_like', {}).get('count'),
            'comment_count': media_info.get('edge_media_to_comment', {}).get('count'),
            'owner': {
                'id': media_info.get('owner', {}).get('id'),
                'username': media_info.get('owner', {}).get('username'),
                'full_name': media_info.get('owner', {}).get('full_name')
            }
        }
        
        # 提取描述
        if self.config.extract_caption:
            try:
                edge_media_to_caption = media_info['edge_media_to_caption']['edges']
                if edge_media_to_caption:
                    metadata['description'] = edge_media_to_caption[0]['node']['text']
            except (KeyError, IndexError):
                pass
                
        # 提取位置
        if self.config.extract_location and 'location' in media_info:
            metadata['location'] = media_info['location']
            
        # 提取标记用户
        if self.config.extract_tagged_users:
            try:
                tagged_users = []
                for edge in media_info['edge_media_to_tagged_user']['edges']:
                    user = edge['node']['user']
                    tagged_users.append({
                        'id': user['id'],
                        'username': user['username'],
                        'full_name': user['full_name']
                    })
                metadata['tagged_users'] = tagged_users
            except KeyError:
                pass
                
        # 提取话题标签
        if self.config.extract_hashtags and metadata['description']:
            hashtags = re.findall(r'#(\w+)', metadata['description'])
            metadata['hashtags'] = hashtags
            
        return metadata
        
    def download(self, url: str) -> Dict[str, Any]:
        """下载Instagram内容。
        
        Args:
            url: 内容URL
            
        Returns:
            Dict[str, Any]: 下载结果
            
        Raises:
            ValueError: URL无效
            DownloadError: 下载失败
        """
        try:
            # 验证URL
            if not self._validate_url(url):
                raise ValueError(f"无效的Instagram URL: {url}")
                
            # 提取媒体信息
            media_info = self._extract_media_info(url)
            
            # 提取媒体URL
            media_urls = self._extract_media_urls(media_info)
            if not media_urls:
                raise DownloadError("未找到可下载的媒体")
                
            # 提取元数据
            metadata = self._extract_metadata(media_info)
            
            # 下载媒体
            downloaded_files = []
            for i, media in enumerate(media_urls):
                try:
                    # 生成文件名
                    filename = self._generate_filename(
                        metadata,
                        media['type'],
                        i + 1 if len(media_urls) > 1 else None
                    )
                    
                    # 下载文件
                    file_path = self._download_media(
                        media['url'],
                        filename
                    )
                    
                    downloaded_files.append({
                        'type': media['type'],
                        'url': media['url'],
                        'file_path': file_path
                    })
                    
                except Exception as e:
                    logger.error(f"下载媒体失败: {e}")
                    
            # 保存元数据
            if downloaded_files:
                metadata_path = self.save_dir / self._generate_metadata_filename(metadata)
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                    
            return {
                'success': bool(downloaded_files),
                'url': url,
                'files': downloaded_files,
                'metadata': metadata
            }
            
        except Exception as e:
            error_msg = f"下载失败: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'url': url,
                'error': error_msg
            }
            
    def _generate_filename(
        self,
        metadata: Dict[str, Any],
        media_type: str,
        index: Optional[int] = None
    ) -> str:
        """生成文件名。
        
        Args:
            metadata: 元数据
            media_type: 媒体类型
            index: 文件索引
            
        Returns:
            str: 文件名
        """
        # 替换模板变量
        filename = self.config.filename_template % {
            'uploader': metadata['owner']['username'],
            'title': metadata.get('title') or metadata['shortcode'],
            'id': metadata['id'],
            'ext': 'mp4' if media_type == 'video' else 'jpg'
        }
        
        # 添加索引
        if index is not None:
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{index}{ext}"
            
        return filename
        
    def _generate_metadata_filename(self, metadata: Dict[str, Any]) -> str:
        """生成元数据文件名。
        
        Args:
            metadata: 元数据
            
        Returns:
            str: 文件名
        """
        return self.config.metadata_template % {
            'uploader': metadata['owner']['username'],
            'title': metadata.get('title') or metadata['shortcode'],
            'id': metadata['id']
        }
        
    def _download_media(self, url: str, filename: str) -> str:
        """下载媒体文件。
        
        Args:
            url: 媒体URL
            filename: 文件名
            
        Returns:
            str: 文件路径
            
        Raises:
            DownloadError: 下载失败
        """
        try:
            # 创建保存目录
            save_path = self.save_dir / filename
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 下载文件
            response = self.session.get(
                url,
                stream=True,
                headers={
                    **self.config.headers,
                    'User-Agent': self.config.user_agent
                }
            )
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            
            # 写入文件
            with open(save_path, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress = downloaded / total_size
                            if self.progress_callback:
                                self.progress_callback(
                                    progress,
                                    f"下载中: {filename} ({downloaded}/{total_size} bytes)"
                                )
                                
            return str(save_path)
            
        except Exception as e:
            raise DownloadError(f"下载媒体文件失败: {e}")
            
    def download_story(
        self,
        url: str,
        save_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """下载Instagram故事。
        
        Args:
            url: 故事URL
            save_dir: 保存目录
            
        Returns:
            Dict[str, Any]: 下载结果
        """
        try:
            # 提取故事ID
            story_id = self._extract_story_id(url)
            if not story_id:
                raise ValueError("无效的故事URL")
                
            # 设置保存目录
            original_dir = None
            if save_dir:
                original_dir = self.save_dir
                self.save_dir = save_dir
                
            try:
                # 下载故事
                result = self.extractor.download_story(
                    story_id,
                    str(self.save_dir),
                    preprocessors=['remove_metadata']
                )
                
                return {
                    'success': True,
                    'url': url,
                    'file_path': result['file_path'],
                    'expires_at': result['expires_at'],
                    'metadata': result['metadata']
                }
                
            finally:
                # 恢复原始保存目录
                if original_dir:
                    self.save_dir = original_dir
                    
        except Exception as e:
            error_msg = f"下载故事失败: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'url': url,
                'error': error_msg
            }
            
    def _extract_story_id(self, url: str) -> Optional[str]:
        """提取故事ID。
        
        Args:
            url: 故事URL
            
        Returns:
            Optional[str]: 故事ID
        """
        try:
            # 从URL中提取ID
            match = re.search(r'stories/(\d+)', url)
            if match:
                return match.group(1)
                
            # 获取页面内容
            response = self.session.get(
                url,
                headers={
                    **self.config.headers,
                    'User-Agent': self.config.user_agent
                }
            )
            response.raise_for_status()
            
            # 从页面中提取ID
            match = re.search(r'"story_id":"(\d+)"', response.text)
            if match:
                return match.group(1)
                
        except Exception as e:
            logger.error(f"提取故事ID失败: {e}")
            
        return None 