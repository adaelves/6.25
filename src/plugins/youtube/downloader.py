"""YouTube视频下载器模块。

该模块负责从YouTube下载视频。
支持4K/HDR和会员视频下载。
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

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError
from src.utils.cookie_manager import CookieManager
from .config import YouTubeDownloaderConfig

logger = logging.getLogger(__name__)

class YouTubeDownloader(BaseDownloader):
    """YouTube视频下载器。
    
    支持以下功能：
    - 4K/HDR视频下载
    - 会员视频下载（需要Cookie）
    - 智能码率选择
    - 自动重试和恢复
    
    Attributes:
        config: YouTubeDownloaderConfig, 下载器配置
    """
    
    # 视频格式定义
    FORMATS = {
        '4k': {
            'id': '4k',
            'label': '2160p (4K)',
            'format_id': 'bestvideo[height=2160][vcodec^=vp09]/bestvideo[height=2160]',
            'requires_ffmpeg': True
        },
        'hdr': {
            'id': 'hdr',
            'label': 'HDR',
            'format_id': 'bestvideo[vcodec^=vp09.2]/bestvideo[vcodec^=av01]',
            'note': '需要HDR设备'
        },
        'member': {
            'id': 'member',
            'label': '会员视频',
            'requires_cookie': True
        },
        '1080p': {
            'id': '1080p',
            'label': '1080p',
            'format_id': 'bestvideo[height=1080]/bestvideo'
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
            cookie_manager=cookie_manager
        )
        self.config = config
        self._setup_yt_dlp()

    def _setup_yt_dlp(self):
        """设置yt-dlp下载器。"""
        self.ydl_opts = {
            # 基本配置
            'format': self._get_format_string(),
            'outtmpl': os.path.join(str(self.config.save_dir), self.config.output_template),
            
            # 网络设置
            'proxy': self.config.proxy,
            'socket_timeout': self.config.timeout,
            'retries': self.config.max_retries,
            'fragment_retries': self.config.max_retries,
            
            # 下载设置
            'ignoreerrors': True,
            'no_warnings': True,
            'quiet': True,
            'extract_flat': False,
            
            # 回调函数
            'progress_hooks': [self._progress_hook],
            'postprocessor_hooks': [self._postprocessor_hook],
            
            # 媒体处理设置
            'merge_output_format': 'mp4',
            'writethumbnail': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            
            # 元数据
            'add_metadata': True,
            'embed_thumbnail': True,
            'embed_subs': True,
            
            # 高级设置
            'concurrent_fragment_downloads': 5,
            'http_chunk_size': 10485760,  # 10MB
            
            # 后处理器
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }, {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
        }

        # 添加Cookie支持
        if self.cookie_manager:
            cookie_file = self.cookie_manager.get_cookie_file("youtube")
            if os.path.exists(cookie_file):
                self.ydl_opts['cookiefile'] = cookie_file

    def _get_format_string(self) -> str:
        """获取格式字符串。

        根据配置和可用性生成格式字符串。

        Returns:
            str: 格式字符串
        """
        format_strings = []
        
        # 检查是否支持4K
        if self.config.enable_4k:
            format_strings.append(self.FORMATS['4k']['format_id'])
            
        # 检查是否支持HDR
        if self.config.enable_hdr:
            format_strings.append(self.FORMATS['hdr']['format_id'])
            
        # 添加默认1080p格式
        format_strings.append(self.FORMATS['1080p']['format_id'])
        
        # 添加音频格式
        format_strings.append('bestaudio[ext=m4a]/bestaudio')
        
        return '/'.join(format_strings)

    def get_formats(self) -> List[Dict[str, Any]]:
        """获取支持的格式列表。

        Returns:
            List[Dict[str, Any]]: 格式列表
        """
        return list(self.FORMATS.values())

    def download(self, url: str) -> Dict[str, Any]:
        """下载YouTube视频。

        支持普通视频、会员视频、4K和HDR视频。

        Args:
            url: 视频URL

        Returns:
            Dict[str, Any]: 下载结果

        Raises:
            DownloadError: 下载失败
        """
        try:
            # 验证URL
            if not self._validate_url(url):
                raise DownloadError("不支持的URL格式")
                
            # 检查会员视频
            if "membership" in url and not self.cookie_manager:
                raise DownloadError("会员视频需要提供Cookie！")
                
            logger.info(f"开始下载视频: {url}")
            
            # 获取视频信息
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise DownloadError("无法获取视频信息")
                    
                # 检查是否为会员视频
                if info.get('premium_only', False) and not self.cookie_manager:
                    raise DownloadError("该视频仅限会员观看，请提供Cookie")
                    
                # 智能选择最佳格式
                best_format = self._select_best_format(info)
                if best_format:
                    self.ydl_opts['format'] = best_format
                    
                # 下载视频
                result = ydl.download([url])
                if result != 0:
                    raise DownloadError("下载失败")
                    
                return {
                    'success': True,
                    'url': url,
                    'info': info,
                    'format': best_format
                }
                
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
            raise DownloadError(f"下载失败: {str(e)}")

    def _select_best_format(self, info: Dict[str, Any]) -> str:
        """智能选择最佳格式。

        根据视频信息和系统配置选择最佳下载格式。

        Args:
            info: 视频信息

        Returns:
            str: 格式字符串
        """
        try:
            formats = info.get('formats', [])
            if not formats:
                return self._get_format_string()
                
            # 检查是否有4K格式
            has_4k = any(f.get('height', 0) == 2160 for f in formats)
            if has_4k and self.config.enable_4k:
                return self.FORMATS['4k']['format_id']
                
            # 检查是否有HDR格式
            has_hdr = any('HDR' in f.get('vcodec', '') for f in formats)
            if has_hdr and self.config.enable_hdr:
                return self.FORMATS['hdr']['format_id']
                
            # 根据带宽选择合适的码率
            if self.config.max_bitrate:
                suitable_formats = [
                    f for f in formats 
                    if f.get('tbr', 0) <= self.config.max_bitrate
                ]
                if suitable_formats:
                    best_format = max(
                        suitable_formats,
                        key=lambda x: (x.get('height', 0), x.get('tbr', 0))
                    )
                    return f"{best_format['format_id']}+bestaudio"
                    
            return self._get_format_string()
            
        except Exception as e:
            logger.warning(f"选择格式失败: {str(e)}")
            return self._get_format_string()

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
        """验证URL是否为有效的YouTube链接。

        Args:
            url: 要验证的URL

        Returns:
            bool: 是否为有效的YouTube链接
        """
        return 'youtube.com' in url or 'youtu.be' in url
