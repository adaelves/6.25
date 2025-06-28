"""YouTube视频下载器模块。

该模块负责从YouTube下载视频。
支持会员视频下载和字幕下载。
自动处理年龄限制和会员限制。
"""

import os
import logging
import json
from typing import Optional, Dict, Any, List, Callable, Union
from pathlib import Path
import yt_dlp
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError, APIError, AgeRestrictedError
from src.utils.cookie_manager import CookieManager
from .config import YouTubeDownloaderConfig

logger = logging.getLogger(__name__)

class YouTubeDownloader(BaseDownloader):
    """YouTube视频下载器。
    
    支持会员视频下载和字幕下载。
    自动处理年龄限制和会员限制。
    
    Attributes:
        config: YouTubeDownloaderConfig, 下载器配置
    """
    
    # 视频格式定义
    FORMAT_PRIORITIES = {
        '4k': {
            'height': 2160,
            'label': '4K',
            'vcodec': ['vp09', 'avc1']
        },
        'hdr': {
            'height': 1440,
            'label': 'HDR',
            'vcodec': ['vp09.2', 'av01']
        },
        'fhd': {
            'height': 1080,
            'label': 'FHD',
            'vcodec': ['avc1', 'vp09']
        },
        'hd': {
            'height': 720,
            'label': 'HD',
            'vcodec': ['avc1', 'vp09']
        }
    }
    
    def __init__(
        self,
        config: YouTubeDownloaderConfig,
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
            platform="youtube",
            save_dir=config.save_dir,
            progress_callback=progress_callback,
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries,
            cookie_manager=cookie_manager,
            config=config
        )
        
        # 设置yt-dlp
        self._setup_yt_dlp()
        
        # 验证Cookie
        if cookie_manager and cookie_manager.get_cookies("youtube"):
            try:
                self._validate_cookie()
                logger.info("YouTube Cookie 验证成功")
            except ValueError as e:
                logger.warning(f"YouTube Cookie 验证失败: {str(e)}")

    def _setup_yt_dlp(self):
        """设置yt-dlp下载器。"""
        self.yt_dlp_opts = {
            # 基本配置
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(str(self.config.save_dir), '%(uploader)s/%(title)s-%(id)s.%(ext)s'),
            
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
            
            # 字幕设置
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['zh-Hans', 'en'],
            'postprocessors': [{
                'key': 'FFmpegEmbedSubtitle',
                'already_have_subtitle': False,
            }],
            
            # 媒体处理设置
            'merge_output_format': 'mp4',
            'writethumbnail': True,
            'embedthumbnail': True,
            
            # 元数据
            'add_metadata': True,
            'addmetadata': True,
            
            # 年龄限制
            'age_limit': 99,
        }

        # 添加Cookie文件
        if self.cookie_manager:
            cookie_file = self.cookie_manager.get_cookie_file("youtube")
            if os.path.exists(cookie_file):
                self.yt_dlp_opts['cookiefile'] = cookie_file

    def get_available_formats(self, url: str) -> List[Dict[str, Any]]:
        """动态获取支持的分辨率。
        
        获取视频支持的所有格式，并按分辨率排序。
        
        Args:
            url: 视频URL
            
        Returns:
            List[Dict[str, Any]]: 格式列表，按分辨率降序排列
            
        Raises:
            DownloadError: 获取格式失败
        """
        try:
            # 创建临时yt-dlp选项
            opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'proxy': self.config.proxy
            }
            
            # 如果有Cookie，添加Cookie
            if self.cookie_manager:
                cookie_file = self.cookie_manager.get_cookie_file("youtube")
                if os.path.exists(cookie_file):
                    opts['cookiefile'] = cookie_file
            
            # 获取视频信息
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise DownloadError("无法获取视频信息")
                    
                formats = info.get('formats', [])
                if not formats:
                    raise DownloadError("无法获取视频格式")
                    
                # 过滤并排序格式
                video_formats = []
                for fmt in formats:
                    # 只保留有分辨率的视频格式
                    if fmt.get('height') and fmt.get('vcodec') != 'none':
                        # 添加格式标签
                        fmt['label'] = self._get_format_label(fmt)
                        video_formats.append(fmt)
                        
                # 按分辨率降序排序
                video_formats.sort(
                    key=lambda x: (x.get('height', 0), x.get('tbr', 0)), 
                    reverse=True
                )
                
                logger.info(f"获取到 {len(video_formats)} 个可用格式")
                return video_formats
                
        except Exception as e:
            logger.error(f"获取视频格式失败: {str(e)}")
            raise DownloadError(f"获取视频格式失败: {str(e)}")

    def _get_format_label(self, fmt: Dict[str, Any]) -> str:
        """获取格式标签。
        
        Args:
            fmt: 格式信息
            
        Returns:
            str: 格式标签
        """
        height = fmt.get('height', 0)
        vcodec = fmt.get('vcodec', '').lower()
        
        # 检查是否是HDR
        is_hdr = any(codec in vcodec for codec in ['vp09.2', 'av01'])
        
        # 获取质量标签
        quality = None
        for name, info in self.FORMAT_PRIORITIES.items():
            if height >= info['height']:
                quality = info['label']
                break
        quality = quality or f"{height}p"
        
        # 构建完整标签
        label_parts = [quality]
        if is_hdr:
            label_parts.append('HDR')
        if fmt.get('fps', 0) > 30:
            label_parts.append(f"{fmt['fps']}fps")
            
        return ' '.join(label_parts)

    def _validate_cookie(self) -> bool:
        """验证Cookie有效性。
        
        检查Cookie是否存在且未过期。
        
        Returns:
            bool: Cookie是否有效
            
        Raises:
            ValueError: Cookie无效或已过期
        """
        try:
            cookies = self.cookie_manager.get_cookies("youtube")
            if not cookies:
                raise ValueError("未找到YouTube Cookie")
                
            # 检查过期时间
            expire_time = None
            for name, value in cookies.items():
                if name.upper() == 'SESSION_EXPIRE':
                    try:
                        expire_time = datetime.fromisoformat(value)
                        break
                    except ValueError:
                        pass
                        
            if not expire_time:
                # 如果没有过期时间，尝试访问会员内容验证
                return self.check_cookie_valid()
                
            # 检查是否过期
            if expire_time <= datetime.now():
                raise ValueError(f"Cookie已过期: {expire_time}")
                
            # 检查是否即将过期（7天内）
            if expire_time <= datetime.now() + timedelta(days=7):
                logger.warning(f"Cookie即将过期: {expire_time}")
                
            return True
            
        except Exception as e:
            raise ValueError(f"验证Cookie失败: {str(e)}")

    def check_cookie_valid(self) -> bool:
        """验证YouTube Cookie是否有效。
        
        通过访问会员专属页面来验证Cookie是否有效。
        
        Returns:
            bool: Cookie是否有效
            
        Raises:
            ValueError: Cookie无效或已过期
        """
        try:
            # 获取Cookie
            cookies = self.cookie_manager.get_cookies("youtube")
            if not cookies:
                raise ValueError("未找到YouTube Cookie")
                
            # 构建请求头
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/91.0.4472.124 Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # 访问会员专属页面
            test_url = "https://www.youtube.com/account"
            response = requests.get(
                test_url,
                headers=headers,
                cookies=cookies,
                proxies={'http': self.proxy, 'https': self.proxy} if self.proxy else None,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # 解析响应
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 检查是否包含会员专享内容标识
            if "会员专享" in response.text or "Premium" in response.text:
                logger.info("YouTube Cookie 验证成功")
                return True
                
            raise ValueError("Cookie无效或已过期")
            
        except requests.RequestException as e:
            raise ValueError(f"验证Cookie时网络错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"验证Cookie失败: {str(e)}")

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
                if self.progress_callback:
                    self.progress_callback(progress, desc)

            elif d['status'] == 'finished':
                logger.info(f"下载完成: {d['filename']}")
                if self.progress_callback:
                    self.progress_callback(1.0, "下载完成")

            elif d['status'] == 'error':
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
        """验证URL是否为有效的YouTube链接。

        Args:
            url: 要验证的URL

        Returns:
            bool: 是否为有效的YouTube链接
        """
        return 'youtube.com' in url or 'youtu.be' in url

    def is_hdr_video(self, format_info: Dict[str, Any]) -> bool:
        """检测视频是否为HDR格式。
        
        通过检查视频格式信息中的dynamic_range字段和format_note字段，
        判断视频是否为HDR格式。
        
        Args:
            format_info: 视频格式信息
            
        Returns:
            bool: 是否为HDR视频
        """
        return any(
            f.get('dynamic_range') == 'HDR' or 
            'hdr' in f.get('format_note', '').lower()
            for f in format_info['formats']
        )

    def handle_age_restricted(self, url: str) -> None:
        """处理年龄限制视频。
        
        检查URL是否需要年龄验证，如果需要则尝试使用Cookie访问。
        
        Args:
            url: 视频URL
            
        Raises:
            AgeRestrictedError: 需要年龄验证但没有Cookie时抛出
        """
        if "age_verification=1" in url or "age_restricted=1" in url:
            logger.warning("需要年龄验证，尝试携带Cookie...")
            if not self.cookie_manager or not self.cookie_manager.get_cookies("youtube"):
                raise AgeRestrictedError("请提供年龄验证Cookie")
            logger.info("已找到Cookie，尝试访问年龄限制视频")

    def download(self, url: str, format_id: Optional[str] = None) -> Dict[str, Any]:
        """下载YouTube视频。
        
        支持指定格式ID下载，自动处理年龄限制。
        
        Args:
            url: 视频URL
            format_id: 格式ID（可选）
            
        Returns:
            Dict[str, Any]: 下载结果
            
        Raises:
            DownloadError: 下载失败
            AgeRestrictedError: 年龄限制且无Cookie
        """
        if not self._validate_url(url):
            raise DownloadError(f"无效的YouTube URL: {url}")
            
        try:
            # 处理年龄限制
            self.handle_age_restricted(url)
            
            # 获取视频信息
            with yt_dlp.YoutubeDL(self.yt_dlp_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise DownloadError("无法获取视频信息")
                    
                # 检测HDR
                is_hdr = self.is_hdr_video(info)
                if is_hdr:
                    logger.info("检测到HDR视频")
                    
                # 如果指定了格式ID，更新下载选项
                if format_id:
                    self.yt_dlp_opts['format'] = format_id
                    
                # 下载视频
                result = ydl.download([url])
                if result != 0:
                    raise DownloadError("下载失败")
                    
                return {
                    'success': True,
                    'url': url,
                    'title': info.get('title', ''),
                    'uploader': info.get('uploader', ''),
                    'duration': info.get('duration', 0),
                    'is_hdr': is_hdr,
                    'format_id': format_id or info.get('format_id', '')
                }
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "age" in error_msg.lower():
                raise AgeRestrictedError("需要年龄验证")
            raise DownloadError(f"下载失败: {error_msg}")
            
        except Exception as e:
            raise DownloadError(f"下载失败: {str(e)}")
