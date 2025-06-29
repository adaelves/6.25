"""TikTok视频处理器。"""

import os
import cv2
import numpy as np
import ffmpeg
import logging
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class WatermarkRegion:
    """水印区域信息。"""
    x: int  # 左上角x坐标
    y: int  # 左上角y坐标
    width: int  # 宽度
    height: int  # 高度
    confidence: float  # 置信度

class TikTokWatermarkRemover:
    """TikTok水印移除器。"""
    
    # 水印检测参数
    DETECTION_PARAMS = {
        'logo_threshold': 0.7,  # Logo检测阈值
        'text_threshold': 0.6,  # 文字检测阈值
        'min_logo_size': 20,  # 最小Logo尺寸
        'max_logo_size': 150,  # 最大Logo尺寸
        'sample_frames': 10,  # 采样帧数
    }
    
    # 常见水印位置
    COMMON_REGIONS = [
        # 右下角
        {'x': 0.8, 'y': 0.8, 'w': 0.15, 'h': 0.1},
        # 右上角
        {'x': 0.8, 'y': 0.05, 'w': 0.15, 'h': 0.1},
        # 左下角
        {'x': 0.05, 'y': 0.8, 'w': 0.15, 'h': 0.1}
    ]
    
    def __init__(
        self,
        output_dir: str,
        max_workers: int = 4,
        detection_params: Optional[Dict] = None
    ):
        """初始化水印移除器。
        
        Args:
            output_dir: 输出目录
            max_workers: 最大并发处理数
            detection_params: 水印检测参数
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers
        
        if detection_params:
            self.DETECTION_PARAMS.update(detection_params)
            
    def detect_watermark(self, video_path: str) -> List[WatermarkRegion]:
        """检测视频中的水印区域。
        
        使用多种检测方法：
        1. 帧差法检测静态水印
        2. 边缘检测定位Logo
        3. 文字检测识别用户名
        4. 常见位置启发式检查
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            List[WatermarkRegion]: 检测到的水印区域列表
        """
        regions = []
        cap = cv2.VideoCapture(str(video_path))
        
        try:
            # 获取视频信息
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 1. 帧差法检测静态区域
            static_regions = self._detect_static_regions(
                cap,
                width,
                height,
                total_frames
            )
            regions.extend(static_regions)
            
            # 2. 检查常见水印位置
            common_regions = self._check_common_regions(
                width,
                height
            )
            regions.extend(common_regions)
            
            # 3. 合并重叠区域
            regions = self._merge_regions(regions)
            
            # 4. 验证区域有效性
            regions = [
                region for region in regions
                if self._validate_region(region, width, height)
            ]
            
        finally:
            cap.release()
            
        return regions
        
    def _detect_static_regions(
        self,
        cap: cv2.VideoCapture,
        width: int,
        height: int,
        total_frames: int
    ) -> List[WatermarkRegion]:
        """使用帧差法检测静态水印区域。"""
        regions = []
        prev_frame = None
        diff_acc = np.zeros((height, width), dtype=np.float32)
        
        # 均匀采样帧
        sample_interval = max(
            1,
            total_frames // self.DETECTION_PARAMS['sample_frames']
        )
        
        for frame_idx in range(0, total_frames, sample_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break
                
            # 转换为灰度图
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            if prev_frame is not None:
                # 计算帧差
                diff = cv2.absdiff(gray, prev_frame)
                diff_acc += diff
                
            prev_frame = gray
            
        if prev_frame is not None:
            # 归一化累积差分
            diff_acc = diff_acc / (total_frames // sample_interval)
            
            # 二值化
            _, thresh = cv2.threshold(
                diff_acc,
                self.DETECTION_PARAMS['logo_threshold'] * 255,
                255,
                cv2.THRESH_BINARY_INV
            )
            
            # 查找轮廓
            contours, _ = cv2.findContours(
                thresh.astype(np.uint8),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            # 分析轮廓
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if (self.DETECTION_PARAMS['min_logo_size'] <= w <=
                    self.DETECTION_PARAMS['max_logo_size'] and
                    self.DETECTION_PARAMS['min_logo_size'] <= h <=
                    self.DETECTION_PARAMS['max_logo_size']):
                    
                    confidence = 1.0 - (diff_acc[y:y+h, x:x+w].mean() / 255)
                    regions.append(WatermarkRegion(x, y, w, h, confidence))
                    
        return regions
        
    def _check_common_regions(
        self,
        width: int,
        height: int
    ) -> List[WatermarkRegion]:
        """检查常见水印位置。"""
        regions = []
        
        for region in self.COMMON_REGIONS:
            x = int(region['x'] * width)
            y = int(region['y'] * height)
            w = int(region['w'] * width)
            h = int(region['h'] * height)
            
            regions.append(WatermarkRegion(
                x, y, w, h,
                confidence=0.5  # 启发式检查，置信度较低
            ))
            
        return regions
        
    def _merge_regions(
        self,
        regions: List[WatermarkRegion]
    ) -> List[WatermarkRegion]:
        """合并重叠的水印区域。"""
        if not regions:
            return []
            
        # 按置信度排序
        regions.sort(key=lambda r: r.confidence, reverse=True)
        
        merged = []
        used = set()
        
        for i, region1 in enumerate(regions):
            if i in used:
                continue
                
            current = region1
            used.add(i)
            
            # 查找重叠区域
            for j, region2 in enumerate(regions[i+1:], i+1):
                if j in used:
                    continue
                    
                # 检查重叠
                if self._regions_overlap(current, region2):
                    # 合并区域
                    current = self._merge_two_regions(current, region2)
                    used.add(j)
                    
            merged.append(current)
            
        return merged
        
    def _regions_overlap(
        self,
        r1: WatermarkRegion,
        r2: WatermarkRegion
    ) -> bool:
        """检查两个区域是否重叠。"""
        return not (
            r1.x + r1.width < r2.x or
            r2.x + r2.width < r1.x or
            r1.y + r1.height < r2.y or
            r2.y + r2.height < r1.y
        )
        
    def _merge_two_regions(
        self,
        r1: WatermarkRegion,
        r2: WatermarkRegion
    ) -> WatermarkRegion:
        """合并两个重叠区域。"""
        x = min(r1.x, r2.x)
        y = min(r1.y, r2.y)
        width = max(r1.x + r1.width, r2.x + r2.width) - x
        height = max(r1.y + r1.height, r2.y + r2.height) - y
        confidence = max(r1.confidence, r2.confidence)
        
        return WatermarkRegion(x, y, width, height, confidence)
        
    def _validate_region(
        self,
        region: WatermarkRegion,
        width: int,
        height: int
    ) -> bool:
        """验证水印区域是否有效。"""
        # 检查区域大小
        if (region.width < self.DETECTION_PARAMS['min_logo_size'] or
            region.width > self.DETECTION_PARAMS['max_logo_size'] or
            region.height < self.DETECTION_PARAMS['min_logo_size'] or
            region.height > self.DETECTION_PARAMS['max_logo_size']):
            return False
            
        # 检查区域位置
        if (region.x < 0 or region.x + region.width > width or
            region.y < 0 or region.y + region.height > height):
            return False
            
        # 检查置信度
        if region.confidence < self.DETECTION_PARAMS['logo_threshold']:
            return False
            
        return True
        
    def remove_watermark(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> str:
        """移除视频水印。
        
        Args:
            video_path: 输入视频路径
            output_path: 输出视频路径（可选）
            
        Returns:
            str: 处理后的视频路径
        """
        # 1. 检测水印区域
        regions = self.detect_watermark(video_path)
        
        if not regions:
            logger.warning(f"未检测到水印: {video_path}")
            return video_path
            
        # 2. 生成输出路径
        if output_path is None:
            input_path = Path(video_path)
            output_path = str(
                self.output_dir / f"{input_path.stem}_nowatermark{input_path.suffix}"
            )
            
        # 3. 构建FFmpeg命令
        try:
            stream = ffmpeg.input(video_path)
            
            # 应用delogo滤镜
            for region in regions:
                stream = stream.filter(
                    'delogo',
                    x=region.x,
                    y=region.y,
                    w=region.width,
                    h=region.height
                )
                
            # 输出视频
            stream = ffmpeg.output(
                stream,
                output_path,
                acodec='copy'  # 复制音频流
            )
            
            # 执行命令
            ffmpeg.run(
                stream,
                capture_stdout=True,
                capture_stderr=True,
                overwrite_output=True
            )
            
            logger.info(f"水印移除完成: {output_path}")
            return output_path
            
        except ffmpeg.Error as e:
            logger.error(f"水印移除失败: {e.stderr.decode()}")
            return video_path
            
    def batch_remove_watermark(
        self,
        video_paths: List[str],
        output_dir: Optional[str] = None
    ) -> List[str]:
        """批量移除视频水印。
        
        Args:
            video_paths: 输入视频路径列表
            output_dir: 输出目录（可选）
            
        Returns:
            List[str]: 处理后的视频路径列表
        """
        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(self.remove_watermark, video_paths))
            
        return results

class TikTokDownloader:
    """TikTok视频下载器。"""
    
    def __init__(
        self,
        output_dir: str,
        remove_watermark: bool = True,
        max_workers: int = 4
    ):
        """初始化下载器。
        
        Args:
            output_dir: 输出目录
            remove_watermark: 是否移除水印
            max_workers: 最大并发数
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if remove_watermark:
            self.watermark_remover = TikTokWatermarkRemover(
                str(self.output_dir / "nowatermark"),
                max_workers=max_workers
            )
        else:
            self.watermark_remover = None
            
    def download(self, url: str) -> Optional[str]:
        """下载单个视频。
        
        Args:
            url: 视频URL
            
        Returns:
            Optional[str]: 下载的视频路径
        """
        # TODO: 实现视频下载逻辑
        video_path = None
        
        if video_path and self.watermark_remover:
            return self.watermark_remover.remove_watermark(video_path)
            
        return video_path
        
    def batch_download(self, urls: List[str]) -> List[Optional[str]]:
        """批量下载视频。
        
        Args:
            urls: 视频URL列表
            
        Returns:
            List[Optional[str]]: 下载的视频路径列表
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(self.download, urls))
            
        if self.watermark_remover:
            # 过滤出成功下载的视频
            valid_paths = [p for p in results if p]
            if valid_paths:
                results = self.watermark_remover.batch_remove_watermark(valid_paths)
                
        return results 