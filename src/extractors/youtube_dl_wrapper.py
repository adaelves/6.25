"""YouTube下载器封装。"""

import os
import json
import logging
from typing import Dict, List, Optional, Union
from yt_dlp import YoutubeDL
from yt_dlp.utils import ISO639Utils

logger = logging.getLogger(__name__)

class YouTubeSubtitle:
    """YouTube字幕处理类。"""
    
    def __init__(self, video_id: str, lang: str = 'zh-Hans'):
        """初始化字幕处理器。
        
        Args:
            video_id: YouTube视频ID
            lang: 目标语言代码，默认简体中文
        """
        self.video_id = video_id
        self.lang = lang
        self._normalize_lang_code()
        
    def _normalize_lang_code(self):
        """标准化语言代码。
        
        将常用的语言代码转换为YouTube支持的格式：
        - zh -> zh-Hans
        - zh-CN -> zh-Hans
        - zh-TW -> zh-Hant
        - en -> en
        """
        lang_map = {
            'zh': 'zh-Hans',
            'zh-CN': 'zh-Hans',
            'zh-TW': 'zh-Hant',
            'en': 'en'
        }
        self.lang = lang_map.get(self.lang, self.lang)
        
    def _get_base_options(self) -> Dict:
        """获取基础下载选项。"""
        return {
            'skip_download': True,  # 仅下载字幕
            'writesubtitles': True,  # 写入字幕文件
            'subtitlesformat': 'srt',  # 输出SRT格式
            'quiet': True,
            'no_warnings': True
        }
        
    def download(self, output_dir: str) -> Dict[str, str]:
        """下载字幕文件。
        
        同时尝试下载CC字幕和自动生成字幕。
        
        Args:
            output_dir: 输出目录路径
            
        Returns:
            Dict[str, str]: 包含两种字幕文件路径的字典
            {
                'manual': 'path/to/manual.srt',  # CC字幕
                'auto': 'path/to/auto.srt'  # 自动生成字幕
            }
        """
        result = {}
        
        # 1. 下载CC字幕
        cc_opts = {
            **self._get_base_options(),
            'subtitleslangs': [self.lang],
            'outtmpl': os.path.join(output_dir, f'{self.video_id}.%(ext)s')
        }
        
        try:
            with YoutubeDL(cc_opts) as ydl:
                info = ydl.extract_info(
                    f'https://www.youtube.com/watch?v={self.video_id}',
                    download=True
                )
                if info.get('requested_subtitles', {}).get(self.lang):
                    result['manual'] = os.path.join(
                        output_dir,
                        f'{self.video_id}.{self.lang}.srt'
                    )
                    logger.info(f"成功下载CC字幕: {result['manual']}")
        except Exception as e:
            logger.warning(f"下载CC字幕失败: {e}")
            
        # 2. 下载自动生成字幕
        auto_opts = {
            **self._get_base_options(),
            'writeautomaticsub': True,
            'subtitleslangs': [self.lang],
            'outtmpl': os.path.join(output_dir, f'{self.video_id}_auto.%(ext)s')
        }
        
        try:
            with YoutubeDL(auto_opts) as ydl:
                info = ydl.extract_info(
                    f'https://www.youtube.com/watch?v={self.video_id}',
                    download=True
                )
                if info.get('requested_automatic_subtitles', {}).get(self.lang):
                    result['auto'] = os.path.join(
                        output_dir,
                        f'{self.video_id}_auto.{self.lang}.srt'
                    )
                    logger.info(f"成功下载自动生成字幕: {result['auto']}")
        except Exception as e:
            logger.warning(f"下载自动生成字幕失败: {e}")
            
        return result
        
    @staticmethod
    def get_available_languages(video_id: str) -> Dict[str, List[str]]:
        """获取视频可用的字幕语言列表。
        
        Args:
            video_id: YouTube视频ID
            
        Returns:
            Dict[str, List[str]]: 可用语言代码列表
            {
                'manual': ['en', 'zh-Hans', ...],  # CC字幕语言
                'auto': ['en', 'zh-Hans', ...]  # 自动字幕语言
            }
        """
        opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True
        }
        
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    f'https://www.youtube.com/watch?v={video_id}',
                    download=False
                )
                return {
                    'manual': list(info.get('subtitles', {}).keys()),
                    'auto': list(info.get('automatic_captions', {}).keys())
                }
        except Exception as e:
            logger.error(f"获取字幕语言列表失败: {e}")
            return {'manual': [], 'auto': []}
            
class YouTubeDLWrapper:
    """YouTube下载器封装类。"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def get_subtitles(
        self,
        video_id: str,
        lang: str = 'zh-Hans'
    ) -> Dict[str, Optional[str]]:
        """下载视频字幕。
        
        Args:
            video_id: YouTube视频ID
            lang: 目标语言代码，默认简体中文
            
        Returns:
            Dict[str, Optional[str]]: 字幕文件路径
            {
                'manual': 'path/to/manual.srt',  # CC字幕
                'auto': 'path/to/auto.srt'  # 自动生成字幕
            }
        """
        subtitle = YouTubeSubtitle(video_id, lang)
        return subtitle.download(self.output_dir)
        
    def get_available_subtitle_languages(self, video_id: str) -> Dict[str, List[str]]:
        """获取视频可用的字幕语言。"""
        return YouTubeSubtitle.get_available_languages(video_id) 