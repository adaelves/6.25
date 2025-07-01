import logging
from pathlib import Path
from typing import Optional
import requests
import re

from .base import BaseDownloader
from ..task import DownloadTask

logger = logging.getLogger(__name__)

class TwitterDownloader(BaseDownloader):
    """Twitter下载器。"""
    
    def __init__(self, task: DownloadTask):
        """初始化下载器。
        
        Args:
            task: 下载任务
        """
        super().__init__(task)
        self._session = requests.Session()
        
    def start(self):
        """开始下载。"""
        try:
            # 获取视频信息
            video_url = self._get_video_url()
            if not video_url:
                raise ValueError("无法获取视频链接")
                
            # 获取文件大小
            response = self._session.head(video_url, allow_redirects=True)
            total_size = int(response.headers.get('content-length', 0))
            
            # 开始下载
            save_path = self._get_save_path('video.mp4')
            downloaded_size = 0
            
            with self._session.get(video_url, stream=True) as response:
                response.raise_for_status()
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self._stop:
                            return
                            
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # 更新进度
                            if total_size:
                                progress = downloaded_size / total_size * 100
                                self._update_progress(progress)
                                
            # 下载完成
            self._on_complete()
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            self._on_error(str(e))
            
    def _get_video_url(self) -> Optional[str]:
        """获取视频链接。
        
        Returns:
            str: 视频链接
        """
        try:
            # 获取推文页面
            response = self._session.get(self.task.url)
            response.raise_for_status()
            
            # 提取视频链接
            pattern = r'https://video\.twimg\.com/[^"\']+\.mp4'
            match = re.search(pattern, response.text)
            
            if match:
                return match.group(0)
                
        except Exception as e:
            logger.error(f"获取视频链接失败: {e}")
            
        return None 