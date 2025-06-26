"""TikTok下载器模块。

提供视频和图片下载功能。
支持代理和自动重试。
"""

import time
import json
import random
import logging
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Literal
from urllib.parse import urlencode, urlparse

from .signature import TikTokSignature, SignatureError

logger = logging.getLogger(__name__)

class DownloadError(Exception):
    """下载错误。"""
    pass

class TikTokDownloader:
    """TikTok下载器。
    
    支持视频和图片下载。
    自动处理签名和代理。
    
    Attributes:
        signature: TikTokSignature, 签名生成器
        proxy: str, 代理地址
        timeout: int, 超时时间(秒)
        max_retries: int, 最大重试次数
        retry_delay: float, 重试延迟(秒)
        platform: str, 平台(ios/android)
    """
    
    # iOS设备列表
    IOS_DEVICES = [
        "iPhone10,3", "iPhone10,6",  # iPhone X
        "iPhone11,2",                # iPhone XS
        "iPhone11,4", "iPhone11,6",  # iPhone XS Max
        "iPhone11,8",                # iPhone XR
        "iPhone12,1",                # iPhone 11
        "iPhone12,3",                # iPhone 11 Pro
        "iPhone12,5",                # iPhone 11 Pro Max
        "iPhone13,1",                # iPhone 12 mini
        "iPhone13,2",                # iPhone 12
        "iPhone13,3",                # iPhone 12 Pro
        "iPhone13,4",                # iPhone 12 Pro Max
        "iPhone14,4",                # iPhone 13 mini
        "iPhone14,5",                # iPhone 13
        "iPhone14,2",                # iPhone 13 Pro
        "iPhone14,3",                # iPhone 13 Pro Max
    ]
    
    # Android设备列表
    ANDROID_DEVICES = [
        "Pixel 4",
        "Pixel 4 XL", 
        "Pixel 5",
        "Pixel 6",
        "Pixel 6 Pro",
        "Samsung Galaxy S21",
        "Samsung Galaxy S21+",
        "Samsung Galaxy S21 Ultra",
        "OnePlus 9",
        "OnePlus 9 Pro",
        "Xiaomi Mi 11",
        "Xiaomi Mi 11 Ultra",
    ]
    
    def __init__(
        self,
        proxy: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        platform: Literal["ios", "android"] = "ios"
    ):
        """初始化下载器。
        
        Args:
            proxy: 代理地址
            timeout: 超时时间
            max_retries: 最大重试次数
            retry_delay: 重试延迟
            platform: 平台(ios/android)
        """
        self.signature = TikTokSignature()
        self.proxy = proxy
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.platform = platform
        
    def _get_user_agent(self) -> str:
        """生成随机User-Agent。
        
        Returns:
            str: User-Agent字符串
        """
        if self.platform == "ios":
            # 随机选择iOS设备
            device = random.choice(self.IOS_DEVICES)
            ios_version = f"{random.randint(14,16)}.{random.randint(0,9)}"
            return (
                f"Mozilla/5.0 (iPhone; CPU iPhone OS {ios_version.replace('.','_')} like Mac OS X) "
                f"AppleWebKit/605.1.15 (KHTML, like Gecko) "
                f"Mobile/15E148"
            )
        else:
            # 随机选择Android设备
            device = random.choice(self.ANDROID_DEVICES)
            android_version = f"{random.randint(10,13)}.{random.randint(0,9)}"
            return (
                f"Mozilla/5.0 (Linux; Android {android_version}; {device}) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{random.randint(90,108)}.0.0.0 Mobile Safari/537.36"
            )
            
    async def _get_direct_url(
        self,
        video_id: str,
        line: str = "0",
        ratio: str = "1080p",
        api_version: str = TikTokSignature.API_V2
    ) -> str:
        """获取视频直连URL。
        
        Args:
            video_id: 视频ID
            line: 线路(0:国内,1:国际)
            ratio: 清晰度
            api_version: API版本
            
        Returns:
            str: 直连URL
            
        Raises:
            DownloadError: 获取失败
        """
        try:
            # 构建参数
            params = {
                "video_id": video_id,
                "line": line,
                "ratio": ratio,
                "device_id": self.signature.device_id
            }
            
            # 添加签名
            try:
                signature = self.signature.sign(params, api_version)
                params["_signature"] = signature
            except SignatureError as e:
                logger.error(f"生成签名失败: {e}")
                raise DownloadError(f"生成签名失败: {e}")
                
            # 构建URL
            base_url = "https://api.tiktokv.com/aweme/v1/play/"
            return f"{base_url}?{urlencode(params)}"
            
        except Exception as e:
            raise DownloadError(f"获取直连URL失败: {e}")
            
    async def _request(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        retry: int = 0
    ) -> aiohttp.ClientResponse:
        """发送HTTP请求。
        
        支持自动重试和代理。
        
        Args:
            url: 请求URL
            params: URL参数
            headers: 请求头
            retry: 当前重试次数
            
        Returns:
            aiohttp.ClientResponse: 响应对象
            
        Raises:
            DownloadError: 请求失败
        """
        try:
            # 添加签名
            if params:
                try:
                    signature = self.signature.sign(params)
                    params["_signature"] = signature
                except SignatureError as e:
                    logger.error(f"生成签名失败: {e}")
                    raise DownloadError(f"生成签名失败: {e}")
                    
            # 设置代理
            if self.proxy:
                proxy = self.proxy
            else:
                proxy = None
                
            # 设置请求头
            if not headers:
                headers = {
                    "User-Agent": self._get_user_agent()
                }
                
            # 发送请求
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    proxy=proxy,
                    timeout=self.timeout
                ) as response:
                    response.raise_for_status()
                    return response
                    
        except asyncio.TimeoutError:
            logger.warning(f"请求超时: {url}")
            if retry < self.max_retries:
                await asyncio.sleep(self.retry_delay * (2 ** retry))
                return await self._request(url, params, headers, retry + 1)
            raise DownloadError(f"请求超时: {url}")
            
        except aiohttp.ClientError as e:
            logger.warning(f"请求失败: {e}")
            if retry < self.max_retries:
                await asyncio.sleep(self.retry_delay * (2 ** retry))
                return await self._request(url, params, headers, retry + 1)
            raise DownloadError(f"请求失败: {e}")
            
    async def download_video(
        self,
        video_id: str,
        save_path: Union[str, Path],
        api_version: str = TikTokSignature.API_V2
    ) -> Path:
        """下载视频。
        
        Args:
            video_id: 视频ID
            save_path: 保存路径
            api_version: API版本
            
        Returns:
            Path: 保存路径
            
        Raises:
            DownloadError: 下载失败
        """
        try:
            # 获取直连URL
            video_url = await self._get_direct_url(video_id, api_version=api_version)
            
            # 下载视频
            response = await self._request(video_url)
            
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
                    
            return save_path
            
        except Exception as e:
            raise DownloadError(f"下载视频失败: {e}")
            
    async def download_image(
        self,
        image_id: str,
        save_path: Union[str, Path],
        api_version: str = TikTokSignature.API_V2
    ) -> Path:
        """下载图片。
        
        Args:
            image_id: 图片ID
            save_path: 保存路径
            api_version: API版本
            
        Returns:
            Path: 保存路径
            
        Raises:
            DownloadError: 下载失败
        """
        try:
            # 获取图片信息
            info_url = f"https://api.tiktok.com/aweme/v1/aweme/detail/"
            params = {
                "aweme_id": image_id,
                "device_id": self.signature.device_id
            }
            
            response = await self._request(info_url, params)
            data = await response.json()
            
            if "aweme_detail" not in data:
                raise DownloadError(f"获取图片信息失败: {data}")
                
            image_url = data["aweme_detail"]["image_post_info"]["images"][0]["display_image"]["url_list"][0]
            
            # 下载图片
            response = await self._request(image_url)
            
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
                    
            return save_path
            
        except Exception as e:
            raise DownloadError(f"下载图片失败: {e}")
            
    async def download_by_url(
        self,
        url: str,
        save_path: Union[str, Path],
        api_version: str = TikTokSignature.API_V2
    ) -> Path:
        """通过URL下载。
        
        自动识别视频和图片。
        
        Args:
            url: TikTok URL
            save_path: 保存路径
            api_version: API版本
            
        Returns:
            Path: 保存路径
            
        Raises:
            DownloadError: 下载失败
        """
        try:
            # 解析URL
            parsed = urlparse(url)
            path = parsed.path.strip("/").split("/")
            
            if len(path) < 2:
                raise DownloadError(f"无效的URL: {url}")
                
            # 获取内容ID
            content_id = path[-1]
            
            # 获取内容类型
            info_url = f"https://api.tiktok.com/aweme/v1/aweme/detail/"
            params = {
                "aweme_id": content_id,
                "device_id": self.signature.device_id
            }
            
            response = await self._request(info_url, params)
            data = await response.json()
            
            if "aweme_detail" not in data:
                raise DownloadError(f"获取内容信息失败: {data}")
                
            # 判断内容类型
            if "video" in data["aweme_detail"]:
                return await self.download_video(content_id, save_path, api_version)
            elif "image_post_info" in data["aweme_detail"]:
                return await self.download_image(content_id, save_path, api_version)
            else:
                raise DownloadError(f"不支持的内容类型: {data}")
                
        except Exception as e:
            raise DownloadError(f"下载失败: {e}")
            
    async def download_user_videos(
        self,
        user_id: str,
        save_dir: Union[str, Path],
        max_videos: Optional[int] = None,
        api_version: str = TikTokSignature.API_V2
    ) -> List[Path]:
        """下载用户视频。
        
        Args:
            user_id: 用户ID
            save_dir: 保存目录
            max_videos: 最大下载数量
            api_version: API版本
            
        Returns:
            List[Path]: 保存路径列表
            
        Raises:
            DownloadError: 下载失败
        """
        try:
            save_dir = Path(save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 获取用户视频列表
            url = f"https://api.tiktok.com/aweme/v1/aweme/post/"
            params = {
                "user_id": user_id,
                "count": 20,
                "max_cursor": 0,
                "device_id": self.signature.device_id
            }
            
            video_paths = []
            video_count = 0
            
            while True:
                response = await self._request(url, params)
                data = await response.json()
                
                if "aweme_list" not in data:
                    break
                    
                for video in data["aweme_list"]:
                    if max_videos and video_count >= max_videos:
                        break
                        
                    video_id = video["aweme_id"]
                    save_path = save_dir / f"{video_id}.mp4"
                    
                    try:
                        path = await self.download_video(video_id, save_path, api_version)
                        video_paths.append(path)
                        video_count += 1
                    except DownloadError as e:
                        logger.error(f"下载视频失败: {e}")
                        continue
                        
                if max_videos and video_count >= max_videos:
                    break
                    
                if not data.get("has_more"):
                    break
                    
                params["max_cursor"] = data["max_cursor"]
                
            return video_paths
            
        except Exception as e:
            raise DownloadError(f"下载用户视频失败: {e}")
            
    async def download_user_images(
        self,
        user_id: str,
        save_dir: Union[str, Path],
        max_images: Optional[int] = None,
        api_version: str = TikTokSignature.API_V2
    ) -> List[Path]:
        """下载用户图片。
        
        Args:
            user_id: 用户ID
            save_dir: 保存目录
            max_images: 最大下载数量
            api_version: API版本
            
        Returns:
            List[Path]: 保存路径列表
            
        Raises:
            DownloadError: 下载失败
        """
        try:
            save_dir = Path(save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 获取用户图片列表
            url = f"https://api.tiktok.com/aweme/v1/aweme/post/"
            params = {
                "user_id": user_id,
                "count": 20,
                "max_cursor": 0,
                "device_id": self.signature.device_id
            }
            
            image_paths = []
            image_count = 0
            
            while True:
                response = await self._request(url, params)
                data = await response.json()
                
                if "aweme_list" not in data:
                    break
                    
                for post in data["aweme_list"]:
                    if max_images and image_count >= max_images:
                        break
                        
                    if "image_post_info" not in post:
                        continue
                        
                    image_id = post["aweme_id"]
                    save_path = save_dir / f"{image_id}.jpg"
                    
                    try:
                        path = await self.download_image(image_id, save_path, api_version)
                        image_paths.append(path)
                        image_count += 1
                    except DownloadError as e:
                        logger.error(f"下载图片失败: {e}")
                        continue
                        
                if max_images and image_count >= max_images:
                    break
                    
                if not data.get("has_more"):
                    break
                    
                params["max_cursor"] = data["max_cursor"]
                
            return image_paths
            
        except Exception as e:
            raise DownloadError(f"下载用户图片失败: {e}") 