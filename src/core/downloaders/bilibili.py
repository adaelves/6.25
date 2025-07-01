import logging
from pathlib import Path
from typing import Optional
import requests
import re
import json

from .base import BaseDownloader
from ..task import DownloadTask

logger = logging.getLogger(__name__)

class BilibiliDownloader(BaseDownloader):
    """Bilibili下载器。"""
    
    def __init__(self, task: DownloadTask):
        """初始化下载器。
        
        Args:
            task: 下载任务
        """
        super().__init__(task)
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com'
        })
        
    def start(self):
        """开始下载。"""
        try:
            # 获取视频信息
            video_info = self._get_video_info()
            if not video_info:
                raise ValueError("无法获取视频信息")
                
            # 获取视频链接
            video_url = video_info['video_url']
            audio_url = video_info.get('audio_url')
            
            # 下载视频
            video_path = self._get_save_path('video.mp4')
            self._download_file(video_url, video_path)
            
            # 下载音频
            if audio_url:
                audio_path = self._get_save_path('audio.mp3')
                self._download_file(audio_url, audio_path)
                
                # 合并音视频
                output_path = self._get_save_path(f"{video_info['title']}.mp4")
                self._merge_video_audio(video_path, audio_path, output_path)
                
                # 删除临时文件
                video_path.unlink()
                audio_path.unlink()
                
            # 下载完成
            self._on_complete()
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            self._on_error(str(e))
            
    def _get_video_info(self) -> Optional[dict]:
        """获取视频信息。
        
        Returns:
            dict: 视频信息
        """
        try:
            # 获取视频ID
            bvid = self._get_bvid()
            if not bvid:
                return None
                
            # 获取视频信息
            api_url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
            response = self._session.get(api_url)
            response.raise_for_status()
            
            data = response.json()
            if data['code'] != 0:
                raise ValueError(data['message'])
                
            # 获取视频下载链接
            cid = data['data']['cid']
            download_url = f'https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=116'
            
            response = self._session.get(download_url)
            response.raise_for_status()
            
            data = response.json()
            if data['code'] != 0:
                raise ValueError(data['message'])
                
            # 返回视频信息
            return {
                'title': data['data']['title'],
                'video_url': data['data']['durl'][0]['url'],
                'audio_url': None  # B站API不提供音频链接
            }
            
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            
        return None
        
    def _get_bvid(self) -> Optional[str]:
        """获取视频ID。
        
        Returns:
            str: 视频ID
        """
        try:
            # 匹配BV号
            pattern = r'BV[a-zA-Z0-9]+'
            match = re.search(pattern, self.task.url)
            
            if match:
                return match.group(0)
                
        except Exception as e:
            logger.error(f"获取视频ID失败: {e}")
            
        return None
        
    def _download_file(self, url: str, path: Path):
        """下载文件。
        
        Args:
            url: 文件链接
            path: 保存路径
        """
        try:
            # 获取文件大小
            response = self._session.head(url, allow_redirects=True)
            total_size = int(response.headers.get('content-length', 0))
            
            # 开始下载
            downloaded_size = 0
            
            with self._session.get(url, stream=True) as response:
                response.raise_for_status()
                
                with open(path, 'wb') as f:
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
                                
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            raise
            
    def _merge_video_audio(self, video_path: Path, audio_path: Path, output_path: Path):
        """合并音视频。
        
        Args:
            video_path: 视频文件路径
            audio_path: 音频文件路径
            output_path: 输出文件路径
        """
        try:
            import ffmpeg
            
            # 合并音视频
            video = ffmpeg.input(str(video_path))
            audio = ffmpeg.input(str(audio_path))
            
            stream = ffmpeg.output(
                video,
                audio,
                str(output_path),
                vcodec='copy',
                acodec='copy'
            )
            
            ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            
        except Exception as e:
            logger.error(f"合并音视频失败: {e}")
            raise 