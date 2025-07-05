"""下载器模块"""

import os
import asyncio
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import yt_dlp

class VideoDownloader:
    """视频下载器类"""
    
    def __init__(
        self,
        download_path: str = "downloads",
        proxy: Optional[str] = None
    ):
        self.download_path = download_path
        self.proxy = proxy
        
        # 确保下载目录存在
        if not os.path.exists(download_path):
            os.makedirs(download_path)
    
    def _get_format(self, format: str, quality: str) -> str:
        """获取下载格式字符串
        
        Args:
            format: 目标格式
            quality: 视频质量
            
        Returns:
            str: yt-dlp格式字符串
        """
        if format == "MP3":
            return "bestaudio/best"
            
        # 视频质量映射
        quality_map = {
            "最高质量": "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best",
            "720p": "bestvideo[height<=720]+bestaudio/best",
            "480p": "bestvideo[height<=480]+bestaudio/best"
        }
        
        return quality_map.get(quality, "bestvideo+bestaudio/best")
    
    def _get_options(
        self,
        format: str,
        quality: str,
        progress_hook: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """获取下载选项
        
        Args:
            format: 目标格式
            quality: 视频质量
            progress_hook: 进度回调
            
        Returns:
            Dict[str, Any]: yt-dlp选项
        """
        options = {
            "format": self._get_format(format, quality),
            "outtmpl": os.path.join(
                self.download_path,
                "%(title)s.%(ext)s"
            ),
            "merge_output_format": format.lower(),
            "writethumbnail": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "zh-CN"],
            "postprocessors": [{
                "key": "FFmpegMetadata",
                "add_metadata": True,
            }]
        }
        
        # 添加MP3后处理器
        if format == "MP3":
            options["postprocessors"].append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            })
        
        # 添加代理
        if self.proxy:
            options["proxy"] = self.proxy
        
        # 添加进度回调
        if progress_hook:
            options["progress_hooks"] = [progress_hook]
        
        return options
    
    async def download(
        self,
        url: str,
        format: str = "MP4",
        quality: str = "1080p",
        progress_hook: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """异步下载视频
        
        Args:
            url: 视频URL
            format: 目标格式
            quality: 视频质量
            progress_hook: 进度回调
            
        Returns:
            Dict[str, Any]: 下载信息
        """
        loop = asyncio.get_event_loop()
        
        # 获取下载选项
        options = self._get_options(format, quality, progress_hook)
        
        try:
            # 创建下载器
            with yt_dlp.YoutubeDL(options) as ydl:
                # 获取视频信息
                info = await loop.run_in_executor(
                    None,
                    lambda: ydl.extract_info(url, download=False)
                )
                
                # 开始下载
                await loop.run_in_executor(
                    None,
                    lambda: ydl.download([url])
                )
                
                # 返回下载信息
                return {
                    "title": info["title"],
                    "duration": info["duration"],
                    "file_path": os.path.join(
                        self.download_path,
                        f"{info['title']}.{format.lower()}"
                    ),
                    "file_size": os.path.getsize(
                        os.path.join(
                            self.download_path,
                            f"{info['title']}.{format.lower()}"
                        )
                    ),
                    "thumbnail": info.get("thumbnail"),
                    "description": info.get("description"),
                    "upload_date": info.get("upload_date"),
                    "uploader": info.get("uploader"),
                    "view_count": info.get("view_count")
                }
                
        except Exception as e:
            raise Exception(f"下载失败: {str(e)}")
    
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息
        
        Args:
            url: 视频URL
            
        Returns:
            Dict[str, Any]: 视频信息
        """
        options = {
            "quiet": True,
            "no_warnings": True
        }
        
        if self.proxy:
            options["proxy"] = self.proxy
        
        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                return ydl.extract_info(url, download=False)
            except Exception as e:
                raise Exception(f"获取视频信息失败: {str(e)}")
    
    def cancel_download(self) -> None:
        """取消下载"""
        # TODO: 实现下载取消功能
        pass 