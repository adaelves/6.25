"""Twitter视频下载器模块。

该模块负责从Twitter下载视频。
支持认证和代理功能。
"""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import yt_dlp

from src.core.downloader import BaseDownloader
from src.core.exceptions import DownloadError
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
        config: TwitterDownloaderConfig
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
                filename = f"{info['title']}_{info['id']}.mp4"
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
                **self.config.to_ydl_opts(),
                'outtmpl': str(save_path),
                'progress_hooks': [self._progress_hook],
                'continuedl': True,
            }
            
            if resume_size > 0:
                ydl_opts.update({
                    'resume': True,
                    'start_byte': resume_size
                })
                
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
            ydl_opts = self.config.to_ydl_opts()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
                
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            raise DownloadError(f"无法提取视频信息: {e}") 