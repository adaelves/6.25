"""Xhamster下载器模块。

提供Xhamster视频的下载功能。
"""

import os
import re
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import yt_dlp

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError
from src.utils.cookie_manager import CookieManager
from .config import XhamsterDownloaderConfig

logger = logging.getLogger(__name__)

class XhamsterDownloader(BaseDownloader):
    """Xhamster下载器。
    
    支持以下功能：
    - 视频下载（支持多种质量）
    - 缩略图下载
    - 预览图下载
    - 元数据提取
    
    Attributes:
        config: XhamsterDownloaderConfig, 下载器配置
    """
    
    # URL正则表达式
    VALID_URL_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?xhamster\.com"
        r"/videos/[^/]+-(\d+)"
    )
    
    # API端点
    API_BASE = "https://xhamster.com/api"
    VIDEO_INFO_URL = f"{API_BASE}/videos/{{video_id}}"
    
    def __init__(
        self,
        config: XhamsterDownloaderConfig,
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
            platform="xhamster",
            save_dir=config.save_dir,
            progress_callback=progress_callback,
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cookie_manager=cookie_manager,
            config=config
        )
        
        self.config = config
        
        # 设置yt-dlp
        self._setup_yt_dlp()
        
    def _setup_yt_dlp(self):
        """设置yt-dlp下载器。"""
        self.yt_dlp_opts = {
            # 基本配置
            'format': f'bestvideo[height<={self.config.quality[:-1]}]+bestaudio/best[height<={self.config.quality[:-1]}]',
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
            cookie_file = self.cookie_manager.get_cookie_file("xhamster")
            if os.path.exists(cookie_file):
                self.yt_dlp_opts['cookiefile'] = cookie_file
                
    def _validate_url(self, url: str) -> bool:
        """验证URL是否为有效的Xhamster链接。
        
        Args:
            url: 要验证的URL
            
        Returns:
            bool: URL是否有效
        """
        return bool(self.VALID_URL_PATTERN.match(url))
        
    def _extract_video_id(self, url: str) -> str:
        """从URL中提取视频ID。
        
        Args:
            url: 视频URL
            
        Returns:
            str: 视频ID
            
        Raises:
            ValueError: URL无效
        """
        match = self.VALID_URL_PATTERN.match(url)
        if not match:
            raise ValueError(f"无效的Xhamster URL: {url}")
        return match.group(1)
        
    def _extract_video_info(self, url: str) -> Dict[str, Any]:
        """提取视频信息。
        
        Args:
            url: 视频URL
            
        Returns:
            Dict[str, Any]: 视频信息
            
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
            
            # 提取视频信息
            video_info = {}
            
            # 提取标题
            if self.config.extract_title:
                title_elem = soup.find('h1', class_='video-title')
                if title_elem:
                    video_info['title'] = title_elem.text.strip()
                    
            # 提取描述
            if self.config.extract_description:
                desc_elem = soup.find('div', class_='video-description')
                if desc_elem:
                    video_info['description'] = desc_elem.text.strip()
                    
            # 提取标签
            if self.config.extract_tags:
                tags = []
                tag_elems = soup.find_all('a', class_='video-tag')
                for tag in tag_elems:
                    tags.append(tag.text.strip())
                video_info['tags'] = tags
                
            # 提取分类
            if self.config.extract_categories:
                categories = []
                cat_elems = soup.find_all('a', class_='video-category')
                for cat in cat_elems:
                    categories.append(cat.text.strip())
                video_info['categories'] = categories
                
            # 提取时长
            if self.config.extract_duration:
                duration_elem = soup.find('div', class_='video-duration')
                if duration_elem:
                    video_info['duration'] = duration_elem.text.strip()
                    
            # 提取观看次数
            if self.config.extract_views:
                views_elem = soup.find('div', class_='video-views')
                if views_elem:
                    video_info['views'] = views_elem.text.strip()
                    
            # 提取评分
            if self.config.extract_rating:
                rating_elem = soup.find('div', class_='video-rating')
                if rating_elem:
                    video_info['rating'] = rating_elem.text.strip()
                    
            # 提取上传者信息
            if self.config.extract_uploader:
                uploader_elem = soup.find('a', class_='video-uploader')
                if uploader_elem:
                    video_info['uploader'] = {
                        'name': uploader_elem.text.strip(),
                        'url': uploader_elem['href']
                    }
                    
            # 提取上传日期
            if self.config.extract_upload_date:
                date_elem = soup.find('div', class_='video-date')
                if date_elem:
                    video_info['upload_date'] = date_elem.text.strip()
                    
            # 提取视频URL
            video_info['video_urls'] = self._extract_video_urls(soup)
            
            # 提取缩略图URL
            if self.config.download_thumbnail:
                thumb_elem = soup.find('meta', property='og:image')
                if thumb_elem:
                    video_info['thumbnail_url'] = thumb_elem['content']
                    
            # 提取预览图URL
            if self.config.download_preview:
                preview_elem = soup.find('div', class_='video-previews')
                if preview_elem:
                    preview_imgs = preview_elem.find_all('img')
                    video_info['preview_urls'] = [img['src'] for img in preview_imgs]
                    
            return video_info
            
        except requests.RequestException as e:
            raise DownloadError(f"获取页面失败: {e}")
        except Exception as e:
            raise DownloadError(f"提取视频信息失败: {e}")
            
    def _extract_video_urls(self, soup: BeautifulSoup) -> Dict[str, str]:
        """提取视频URL。
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Dict[str, str]: 不同质量的视频URL
        """
        video_urls = {}
        
        try:
            # 查找包含视频URL的脚本
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'window.initials' in script.string:
                    # 提取JSON数据
                    json_str = re.search(r'window\.initials\s*=\s*({.*?});', script.string)
                    if json_str:
                        data = json.loads(json_str.group(1))
                        
                        # 提取不同质量的视频URL
                        if 'videoModel' in data and 'sources' in data['videoModel']:
                            sources = data['videoModel']['sources']
                            for quality, url in sources.items():
                                video_urls[quality] = url
                                
        except Exception as e:
            logger.error(f"提取视频URL失败: {e}")
            
        return video_urls
        
    def download(self, url: str) -> Dict[str, Any]:
        """下载Xhamster视频。
        
        Args:
            url: 视频URL
            
        Returns:
            Dict[str, Any]: 下载结果
            
        Raises:
            ValueError: URL无效
            DownloadError: 下载失败
        """
        try:
            # 验证URL
            if not self._validate_url(url):
                raise ValueError(f"无效的Xhamster URL: {url}")
                
            # 提取视频信息
            video_info = self._extract_video_info(url)
            
            # 选择视频质量
            video_url = self._select_video_url(video_info['video_urls'])
            if not video_url:
                raise DownloadError("未找到可下载的视频")
                
            # 生成文件名
            filename = self._generate_filename(video_info)
            
            # 下载视频
            video_path = self._download_video(video_url, filename)
            
            # 下载缩略图
            thumbnail_path = None
            if self.config.download_thumbnail and 'thumbnail_url' in video_info:
                thumbnail_path = self._download_thumbnail(
                    video_info['thumbnail_url'],
                    filename
                )
                
            # 下载预览图
            preview_paths = []
            if self.config.download_preview and 'preview_urls' in video_info:
                preview_paths = self._download_previews(
                    video_info['preview_urls'],
                    filename
                )
                
            # 保存元数据
            metadata_path = self._save_metadata(video_info, filename)
            
            return {
                'success': True,
                'url': url,
                'video_path': video_path,
                'thumbnail_path': thumbnail_path,
                'preview_paths': preview_paths,
                'metadata_path': metadata_path,
                'metadata': video_info
            }
            
        except Exception as e:
            error_msg = f"下载失败: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'url': url,
                'error': error_msg
            }
            
    def _select_video_url(self, video_urls: Dict[str, str]) -> Optional[str]:
        """选择合适质量的视频URL。
        
        Args:
            video_urls: 不同质量的视频URL
            
        Returns:
            Optional[str]: 选中的视频URL
        """
        # 质量优先级
        qualities = ['1080p', '720p', '480p', '240p']
        
        # 从配置的质量开始查找
        start_index = qualities.index(self.config.quality)
        for quality in qualities[start_index:]:
            if quality in video_urls:
                return video_urls[quality]
                
        # 如果没有找到配置的质量，选择可用的最高质量
        for quality in qualities[:start_index][::-1]:
            if quality in video_urls:
                return video_urls[quality]
                
        return None
        
    def _generate_filename(self, video_info: Dict[str, Any]) -> str:
        """生成文件名。
        
        Args:
            video_info: 视频信息
            
        Returns:
            str: 文件名
        """
        # 提取视频ID
        video_id = self._extract_video_id(video_info.get('url', ''))
        
        # 替换模板变量
        return self.config.filename_template % {
            'title': video_info.get('title', 'untitled'),
            'id': video_id,
            'ext': 'mp4'
        }
        
    def _download_video(self, url: str, filename: str) -> str:
        """下载视频文件。
        
        Args:
            url: 视频URL
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
            raise DownloadError(f"下载视频文件失败: {e}")
            
    def _download_thumbnail(self, url: str, video_filename: str) -> Optional[str]:
        """下载缩略图。
        
        Args:
            url: 缩略图URL
            video_filename: 视频文件名
            
        Returns:
            Optional[str]: 文件路径
        """
        try:
            # 生成缩略图文件名
            name, _ = os.path.splitext(video_filename)
            filename = f"{name}.jpg"
            
            # 下载缩略图
            save_path = self.save_dir / filename
            response = self.session.get(url)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
                
            return str(save_path)
            
        except Exception as e:
            logger.error(f"下载缩略图失败: {e}")
            return None
            
    def _download_previews(
        self,
        urls: List[str],
        video_filename: str
    ) -> List[str]:
        """下载预览图。
        
        Args:
            urls: 预览图URL列表
            video_filename: 视频文件名
            
        Returns:
            List[str]: 文件路径列表
        """
        preview_paths = []
        
        try:
            # 生成预览图目录
            name, _ = os.path.splitext(video_filename)
            preview_dir = self.save_dir / f"{name}_previews"
            preview_dir.mkdir(parents=True, exist_ok=True)
            
            # 下载预览图
            for i, url in enumerate(urls):
                try:
                    filename = f"preview_{i+1}.jpg"
                    save_path = preview_dir / filename
                    
                    response = self.session.get(url)
                    response.raise_for_status()
                    
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                        
                    preview_paths.append(str(save_path))
                    
                except Exception as e:
                    logger.error(f"下载预览图失败: {e}")
                    
        except Exception as e:
            logger.error(f"创建预览图目录失败: {e}")
            
        return preview_paths
        
    def _save_metadata(self, video_info: Dict[str, Any], video_filename: str) -> str:
        """保存元数据。
        
        Args:
            video_info: 视频信息
            video_filename: 视频文件名
            
        Returns:
            str: 元数据文件路径
        """
        try:
            # 生成元数据文件名
            name, _ = os.path.splitext(video_filename)
            filename = f"{name}.info.json"
            
            # 保存元数据
            save_path = self.save_dir / filename
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(video_info, f, ensure_ascii=False, indent=2)
                
            return str(save_path)
            
        except Exception as e:
            logger.error(f"保存元数据失败: {e}")
            return "" 