"""哔哩哔哩视频提取器。"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum, auto

logger = logging.getLogger(__name__)

class VideoFormat(Enum):
    """视频格式枚举。"""
    FLV = 'flv'
    MP4 = 'mp4'
    DASH = 'dash'

class VideoQuality(Enum):
    """视频画质枚举。"""
    Q_4K = 120  # 4K
    Q_1080P_60 = 116  # 1080P 60帧
    Q_1080P_PLUS = 112  # 1080P+
    Q_1080P = 80  # 1080P
    Q_720P_60 = 74  # 720P 60帧
    Q_720P = 64  # 720P
    Q_480P = 32  # 480P
    Q_360P = 16  # 360P

@dataclass
class VideoStream:
    """视频流信息。"""
    quality: VideoQuality
    format: VideoFormat
    url: str
    size: int
    codec: str
    width: int
    height: int
    fps: int
    bitrate: int

class BilibiliFormatSelector:
    """B站视频格式选择器。"""
    
    # 画质优先级列表（从高到低）
    QUALITY_PRIORITY = [
        VideoQuality.Q_4K,
        VideoQuality.Q_1080P_60,
        VideoQuality.Q_1080P_PLUS,
        VideoQuality.Q_1080P,
        VideoQuality.Q_720P_60,
        VideoQuality.Q_720P,
        VideoQuality.Q_480P,
        VideoQuality.Q_360P
    ]
    
    # 格式优先级列表（从高到低）
    FORMAT_PRIORITY = [
        VideoFormat.FLV,
        VideoFormat.MP4,
        VideoFormat.DASH
    ]
    
    def __init__(self, formats: List[Dict]):
        """初始化格式选择器。
        
        Args:
            formats: 原始格式列表
        """
        self.formats = formats
        self.streams = self._parse_formats()
        
    def _parse_formats(self) -> List[VideoStream]:
        """解析原始格式列表。
        
        Returns:
            List[VideoStream]: 视频流列表
        """
        streams = []
        for fmt in self.formats:
            try:
                quality = VideoQuality(fmt['quality'])
                format_type = VideoFormat(fmt.get('format', 'dash').lower())
                
                stream = VideoStream(
                    quality=quality,
                    format=format_type,
                    url=fmt['url'],
                    size=fmt.get('filesize', 0),
                    codec=fmt.get('codec', ''),
                    width=fmt.get('width', 0),
                    height=fmt.get('height', 0),
                    fps=fmt.get('fps', 0),
                    bitrate=fmt.get('bitrate', 0)
                )
                streams.append(stream)
                
            except (ValueError, KeyError) as e:
                logger.warning(f"解析格式信息失败: {e}")
                continue
                
        return streams
        
    def get_4k_flv(self) -> Optional[VideoStream]:
        """获取4K FLV格式，如果不可用则智能降级。
        
        优先级顺序：
        1. 4K FLV
        2. 4K MP4
        3. 4K DASH
        4. 1080P60 FLV
        5. 1080P+ FLV
        ...以此类推
        
        Returns:
            Optional[VideoStream]: 最佳视频流
        """
        # 1. 尝试获取4K FLV
        stream = self._get_stream(VideoQuality.Q_4K, VideoFormat.FLV)
        if stream:
            logger.info("找到4K FLV格式")
            return stream
            
        # 2. 4K格式降级
        logger.info("4K FLV不可用，尝试其他4K格式")
        for fmt in [VideoFormat.MP4, VideoFormat.DASH]:
            stream = self._get_stream(VideoQuality.Q_4K, fmt)
            if stream:
                logger.info(f"降级到4K {fmt.value}")
                return stream
                
        # 3. 画质降级
        logger.info("4K格式不可用，尝试降级画质")
        return self._fallback_by_quality()
        
    def _get_stream(
        self,
        quality: VideoQuality,
        format_type: VideoFormat
    ) -> Optional[VideoStream]:
        """获取指定画质和格式的视频流。"""
        for stream in self.streams:
            if (stream.quality == quality and 
                stream.format == format_type):
                return stream
        return None
        
    def _fallback_by_quality(self) -> Optional[VideoStream]:
        """按画质优先级降级。"""
        # 跳过4K，从1080P60开始降级
        for quality in self.QUALITY_PRIORITY[1:]:
            # 按格式优先级尝试
            for fmt in self.FORMAT_PRIORITY:
                stream = self._get_stream(quality, fmt)
                if stream:
                    logger.info(f"降级到 {quality.name} {fmt.value}")
                    return stream
        return None
        
    def get_best_quality(self) -> Optional[VideoStream]:
        """获取最高画质的视频流。"""
        for quality in self.QUALITY_PRIORITY:
            for fmt in self.FORMAT_PRIORITY:
                stream = self._get_stream(quality, fmt)
                if stream:
                    return stream
        return None
        
    def get_all_qualities(self) -> List[Tuple[VideoQuality, List[VideoFormat]]]:
        """获取所有可用画质及其对应的格式列表。
        
        Returns:
            List[Tuple[VideoQuality, List[VideoFormat]]]: 
            画质和格式列表的元组列表
        """
        result = []
        for quality in self.QUALITY_PRIORITY:
            formats = []
            for fmt in self.FORMAT_PRIORITY:
                if self._get_stream(quality, fmt):
                    formats.append(fmt)
            if formats:
                result.append((quality, formats))
        return result

class BilibiliExtractor:
    """B站视频提取器。"""
    
    def __init__(self, formats: List[Dict]):
        """初始化提取器。
        
        Args:
            formats: 原始格式列表
        """
        self.selector = BilibiliFormatSelector(formats)
        
    def get_4k_flv(self) -> Optional[VideoStream]:
        """获取4K FLV格式（支持智能降级）。"""
        return self.selector.get_4k_flv()
        
    def get_best_quality(self) -> Optional[VideoStream]:
        """获取最高画质格式。"""
        return self.selector.get_best_quality()
        
    def get_available_qualities(self) -> List[Tuple[VideoQuality, List[VideoFormat]]]:
        """获取所有可用画质。"""
        return self.selector.get_all_qualities() 