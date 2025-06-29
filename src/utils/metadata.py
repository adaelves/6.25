"""元数据工具。

提供元数据处理相关的工具类。
"""

import logging
import os
from typing import Optional, List
import piexif
from PIL import Image
import ffmpeg

from ..exceptions import MetadataError

logger = logging.getLogger(__name__)

class MetadataCleaner:
    """元数据清理器。
    
    提供以下功能：
    1. 清理图片元数据
    2. 清理视频元数据
    3. 选择性保留元数据
    
    Attributes:
        output_dir: 输出目录
        keep_fields: 保留字段列表
    """
    
    # 默认保留的元数据字段
    DEFAULT_KEEP_FIELDS = [
        'Orientation',
        'DateTime',
        'Make',
        'Model'
    ]
    
    def __init__(
        self,
        output_dir: Optional[str] = None,
        keep_fields: Optional[List[str]] = None
    ):
        """初始化清理器。
        
        Args:
            output_dir: 输出目录，可选
            keep_fields: 保留字段列表，可选
        """
        self.output_dir = output_dir or "cleaned"
        self.keep_fields = keep_fields or self.DEFAULT_KEEP_FIELDS
        os.makedirs(self.output_dir, exist_ok=True)
        
    def clean(self, input_path: str) -> str:
        """清理文件元数据。
        
        Args:
            input_path: 输入文件路径
            
        Returns:
            str: 输出文件路径
            
        Raises:
            MetadataError: 处理失败
        """
        try:
            # 获取文件类型
            ext = os.path.splitext(input_path)[1].lower()
            
            # 根据文件类型选择清理方法
            if ext in ['.jpg', '.jpeg']:
                return self._clean_jpeg(input_path)
            elif ext in ['.png']:
                return self._clean_png(input_path)
            elif ext in ['.mp4', '.mov', '.avi']:
                return self._clean_video(input_path)
            else:
                raise MetadataError(f"Unsupported file type: {ext}")
                
        except Exception as e:
            logger.error(f"Failed to clean metadata: {e}")
            raise MetadataError(f"Failed to clean metadata: {e}")
            
    def _clean_jpeg(self, input_path: str) -> str:
        """清理JPEG元数据。
        
        Args:
            input_path: 输入文件路径
            
        Returns:
            str: 输出文件路径
        """
        try:
            # 生成输出路径
            filename = os.path.basename(input_path)
            output_path = os.path.join(
                self.output_dir,
                f"cleaned_{filename}"
            )
            
            # 读取图片
            image = Image.open(input_path)
            
            # 读取EXIF数据
            exif_dict = piexif.load(image.info["exif"])
            
            # 清理不需要保留的字段
            for ifd in exif_dict:
                if isinstance(exif_dict[ifd], dict):
                    keys = list(exif_dict[ifd].keys())
                    for key in keys:
                        tag_name = piexif.TAGS[ifd][key]["name"]
                        if tag_name not in self.keep_fields:
                            del exif_dict[ifd][key]
                            
            # 保存图片
            exif_bytes = piexif.dump(exif_dict)
            image.save(
                output_path,
                "jpeg",
                exif=exif_bytes,
                quality="keep"
            )
            
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to clean JPEG metadata: {e}")
            raise MetadataError(f"Failed to clean JPEG metadata: {e}")
            
    def _clean_png(self, input_path: str) -> str:
        """清理PNG元数据。
        
        Args:
            input_path: 输入文件路径
            
        Returns:
            str: 输出文件路径
        """
        try:
            # 生成输出路径
            filename = os.path.basename(input_path)
            output_path = os.path.join(
                self.output_dir,
                f"cleaned_{filename}"
            )
            
            # 读取图片
            image = Image.open(input_path)
            
            # 创建新图片（不包含元数据）
            image.save(
                output_path,
                "png",
                optimize=True
            )
            
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to clean PNG metadata: {e}")
            raise MetadataError(f"Failed to clean PNG metadata: {e}")
            
    def _clean_video(self, input_path: str) -> str:
        """清理视频元数据。
        
        Args:
            input_path: 输入文件路径
            
        Returns:
            str: 输出文件路径
        """
        try:
            # 生成输出路径
            filename = os.path.basename(input_path)
            output_path = os.path.join(
                self.output_dir,
                f"cleaned_{filename}"
            )
            
            # 使用ffmpeg清理元数据
            stream = ffmpeg.input(input_path)
            stream = ffmpeg.output(
                stream,
                output_path,
                map_metadata=-1
            )
            
            ffmpeg.run(
                stream,
                capture_stdout=True,
                capture_stderr=True
            )
            
            return output_path
            
        except ffmpeg.Error as e:
            logger.error(f"Failed to clean video metadata: {e.stderr.decode()}")
            raise MetadataError(f"Failed to clean video metadata: {e.stderr.decode()}")
            
    def set_keep_fields(self, fields: List[str]):
        """设置保留字段。
        
        Args:
            fields: 字段列表
        """
        self.keep_fields = fields 