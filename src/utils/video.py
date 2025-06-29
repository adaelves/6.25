"""视频工具。

提供视频处理相关的工具类。
"""

import logging
import os
from typing import Optional, Tuple
import ffmpeg

from ..exceptions import VideoProcessError

logger = logging.getLogger(__name__)

class VideoProcessor:
    """视频处理器。
    
    提供以下功能：
    1. 视频压缩
    2. 格式转换
    3. 分辨率调整
    4. 元数据处理
    
    Attributes:
        output_dir: 输出目录
    """
    
    def __init__(self, output_dir: Optional[str] = None):
        """初始化处理器。
        
        Args:
            output_dir: 输出目录，可选
        """
        self.output_dir = output_dir or "processed"
        os.makedirs(self.output_dir, exist_ok=True)
        
    def compress_to_1080p(
        self,
        input_path: str,
        bitrate: str = "2M",
        codec: str = "libx264"
    ) -> str:
        """压缩视频到1080p。
        
        Args:
            input_path: 输入文件路径
            bitrate: 比特率，默认2M
            codec: 编码器，默认libx264
            
        Returns:
            str: 输出文件路径
            
        Raises:
            VideoProcessError: 处理失败
        """
        try:
            # 获取视频信息
            probe = ffmpeg.probe(input_path)
            video_info = next(
                stream for stream in probe['streams']
                if stream['codec_type'] == 'video'
            )
            
            # 获取原始分辨率
            width = int(video_info['width'])
            height = int(video_info['height'])
            
            # 计算目标分辨率
            target_height = 1080
            target_width = int(width * (target_height / height))
            
            # 确保宽度是2的倍数
            target_width = (target_width // 2) * 2
            
            # 生成输出路径
            filename = os.path.basename(input_path)
            output_path = os.path.join(
                self.output_dir,
                f"compressed_{filename}"
            )
            
            # 压缩视频
            stream = ffmpeg.input(input_path)
            stream = ffmpeg.filter(
                stream,
                'scale',
                width=target_width,
                height=target_height
            )
            stream = ffmpeg.output(
                stream,
                output_path,
                video_bitrate=bitrate,
                vcodec=codec
            )
            
            ffmpeg.run(
                stream,
                capture_stdout=True,
                capture_stderr=True
            )
            
            return output_path
            
        except ffmpeg.Error as e:
            logger.error(f"Failed to compress video: {e.stderr.decode()}")
            raise VideoProcessError(f"Failed to compress video: {e.stderr.decode()}")
            
    def convert_format(
        self,
        input_path: str,
        output_format: str = "mp4"
    ) -> str:
        """转换视频格式。
        
        Args:
            input_path: 输入文件路径
            output_format: 输出格式，默认mp4
            
        Returns:
            str: 输出文件路径
            
        Raises:
            VideoProcessError: 处理失败
        """
        try:
            # 生成输出路径
            filename = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(
                self.output_dir,
                f"{filename}.{output_format}"
            )
            
            # 转换格式
            stream = ffmpeg.input(input_path)
            stream = ffmpeg.output(stream, output_path)
            
            ffmpeg.run(
                stream,
                capture_stdout=True,
                capture_stderr=True
            )
            
            return output_path
            
        except ffmpeg.Error as e:
            logger.error(f"Failed to convert video format: {e.stderr.decode()}")
            raise VideoProcessError(f"Failed to convert video format: {e.stderr.decode()}")
            
    def get_video_info(self, input_path: str) -> dict:
        """获取视频信息。
        
        Args:
            input_path: 输入文件路径
            
        Returns:
            dict: 视频信息
            
        Raises:
            VideoProcessError: 处理失败
        """
        try:
            probe = ffmpeg.probe(input_path)
            video_info = next(
                stream for stream in probe['streams']
                if stream['codec_type'] == 'video'
            )
            
            return {
                'width': int(video_info['width']),
                'height': int(video_info['height']),
                'duration': float(probe['format']['duration']),
                'bitrate': int(probe['format']['bit_rate']),
                'codec': video_info['codec_name'],
                'format': probe['format']['format_name']
            }
            
        except ffmpeg.Error as e:
            logger.error(f"Failed to get video info: {e.stderr.decode()}")
            raise VideoProcessError(f"Failed to get video info: {e.stderr.decode()}")
            
    def extract_thumbnail(
        self,
        input_path: str,
        time: float = 0,
        size: Optional[Tuple[int, int]] = None
    ) -> str:
        """提取视频缩略图。
        
        Args:
            input_path: 输入文件路径
            time: 时间点(秒)，默认0
            size: 尺寸(宽,高)，可选
            
        Returns:
            str: 输出文件路径
            
        Raises:
            VideoProcessError: 处理失败
        """
        try:
            # 生成输出路径
            filename = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(
                self.output_dir,
                f"{filename}_thumb.jpg"
            )
            
            # 构建命令
            stream = ffmpeg.input(input_path, ss=time)
            if size:
                stream = ffmpeg.filter(
                    stream,
                    'scale',
                    width=size[0],
                    height=size[1]
                )
            stream = ffmpeg.output(
                stream,
                output_path,
                vframes=1
            )
            
            ffmpeg.run(
                stream,
                capture_stdout=True,
                capture_stderr=True
            )
            
            return output_path
            
        except ffmpeg.Error as e:
            logger.error(f"Failed to extract thumbnail: {e.stderr.decode()}")
            raise VideoProcessError(f"Failed to extract thumbnail: {e.stderr.decode()}") 