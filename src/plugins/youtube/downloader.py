"""YouTube视频下载器模块。

该模块负责从YouTube下载视频。
支持断点续传功能。
"""

import os
import logging
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import yt_dlp

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError
from src.core.speed_limiter import SpeedLimiter
from .extractor import YouTubeExtractor
from .config import YouTubeDownloaderConfig

logger = logging.getLogger(__name__)

class YouTubeDownloader(BaseDownloader):
    """YouTube视频下载器。
    
    使用yt-dlp库从YouTube下载视频。
    支持视频质量选择和格式控制。
    支持断点续传功能。
    支持速度限制和并发控制。
    
    Attributes:
        config: YouTubeDownloaderConfig, 下载器配置
        progress_callback: Optional[Callable], 进度回调函数
        speed_limiter: Optional[SpeedLimiter], 速度限制器
        max_height: int, 最大视频高度（像素）
        prefer_quality: str, 优先选择的视频质量
        merge_output_format: str, 合并后的输出格式
    """
    
    # 支持的视频质量
    QUALITIES = {
        '4K': 2160,
        '2K': 1440,
        '1080p': 1080,
        '720p': 720,
        '480p': 480,
        '360p': 360
    }
    
    def __init__(
        self,
        config: YouTubeDownloaderConfig
    ):
        """初始化下载器。
        
        Args:
            config: 下载器配置
        """
        super().__init__(
            save_dir=str(config.save_dir),
            proxy=config.proxy,
            timeout=config.timeout,
            max_retries=config.max_retries
        )
        self.config = config
        self.max_height = config.max_height
        self.prefer_quality = config.prefer_quality
        self.merge_output_format = config.merge_output_format
        self.speed_limiter = (
            SpeedLimiter(config.speed_limit) if config.speed_limit is not None and config.speed_limit > 0 else None
        )
        
    def _get_format_selector(self) -> str:
        """获取格式选择器。
        
        Returns:
            str: 格式选择器字符串
        """
        height = self.QUALITIES.get(self.prefer_quality, 1080)
        height = min(height, self.max_height)
        
        return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
        
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
                
                # 应用速度限制
                if self.speed_limiter and speed and speed > self.config.speed_limit:
                    try:
                        self.speed_limiter.wait_sync(
                            int(speed * self.config.chunk_size / 1024)
                        )
                        speed = self.speed_limiter.current_speed
                    except (TypeError, ValueError) as e:
                        logger.warning(f"速度限制计算出错: {e}")
                        speed = 0
                
                speed_text = f"{speed/1024:.1f} KB/s" if speed else "Unknown"
                eta_text = f"{eta}s" if eta else "Unknown"
                
                self.update_progress(
                    progress,
                    f"下载进度: {downloaded}/{total} bytes"
                    f" ({speed_text}, ETA: {eta_text})"
                )
                
    def download(self, url: str, save_path: Optional[Path] = None) -> bool:
        """下载视频。
        
        Args:
            url: 视频URL
            save_path: 可选的保存路径
            
        Returns:
            bool: 是否下载成功
            
        Raises:
            ValueError: URL无效
            DownloadError: 下载失败
        """
        try:
            # 确定保存路径
            if save_path is None:
                info = self.get_video_info(url)
                filename = f"{info['title']}_{info['quality']}.{self.merge_output_format}"
                filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
                save_path = self.config.save_dir / filename
                
            # 确保输出目录存在
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 检查临时文件
            temp_path = save_path.with_suffix(save_path.suffix + '.part')
            resume_size = temp_path.stat().st_size if temp_path.exists() else 0
            
            if resume_size > 0:
                logger.info(f"发现未完成的下载: {temp_path}, 已下载: {resume_size} 字节")
            
            # yt-dlp配置
            ydl_opts = {
                'format': self._get_format_selector(),
                'outtmpl': str(save_path),
                'merge_output_format': self.merge_output_format,
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,  # 避免证书问题
                'noplaylist': True,  # 不下载播放列表
                'progress_hooks': [self._progress_hook],  # 进度回调
                'continuedl': True,  # 启用断点续传
                'noresizebuffer': True,  # 禁用缓冲区大小调整
                'retries': self.config.max_retries,  # 重试次数
                'fragment_retries': self.config.max_retries,  # 分段重试次数
                'socket_timeout': self.config.timeout,  # 超时设置
            }
            
            if resume_size > 0:
                ydl_opts.update({
                    'resume': True,  # 启用续传
                    'start_byte': resume_size  # 设置起始字节
                })
            
            if self.config.proxy:
                ydl_opts['proxy'] = self.config.proxy
                
            # 下载视频
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            return True
            
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"下载失败: {e}")
            raise DownloadError(str(e))
        except Exception as e:
            logger.error(f"下载失败: {e}")
            raise DownloadError(str(e))
            
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
            extractor = YouTubeExtractor(
                proxy=self.config.proxy,
                timeout=self.config.timeout
            )
            info = extractor.extract_info(url)
            info['quality'] = self.prefer_quality
            return info
            
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            raise DownloadError(str(e)) 