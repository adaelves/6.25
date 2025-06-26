"""B站视频信息提取模块。

该模块负责从B站视频页面和API提取视频信息。
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
import requests
from bs4 import BeautifulSoup
from src.services.proxy import get_current_proxy
from .sign import BiliWbiSign
from core.exceptions import (
    BiliBiliError,
    VIPContentError,
    RegionLockError,
    NetworkError,
    ParsingError,
    RateLimitError
)

logger = logging.getLogger(__name__)

class BilibiliExtractor:
    """B站视频信息提取器。
    
    负责从B站视频页面和API提取视频信息。
    支持普通视频和番剧。
    
    Attributes:
        sessdata: str, B站登录凭证
        proxy: str, 代理服务器地址
        signer: BiliWbiSign, WBI签名生成器
    """
    
    # API端点
    API_VIDEO_INFO = "https://api.bilibili.com/x/web-interface/view"
    API_PLAYURL = "https://api.bilibili.com/x/player/playurl"
    API_BANGUMI_INFO = "https://api.bilibili.com/pgc/view/web/season"
    
    # 视频质量映射
    QUALITY_MAP = {
        127: "8K",           # 大会员专享
        126: "Dolby Vision", # 大会员专享
        120: "4K",          # 大会员专享
        116: "1080p60",     # 大会员专享
        112: "1080p+",      # 大会员专享
        80: "1080p",        # 登录用户
        74: "720p60",       # 登录用户
        64: "720p",         # 登录用户
        32: "480p",         # 所有用户
        16: "360p"          # 所有用户
    }
    
    # 错误代码映射
    ERROR_CODE_MAP = {
        -404: (VIPContentError, "视频不存在或为大会员专享"),
        62002: (RegionLockError, "当前地区不可观看"),
        -403: (RateLimitError, "请求被拦截"),
        -412: (RateLimitError, "请求过于频繁"),
        -101: (ParsingError, "视频已被删除"),
    }
    
    def __init__(self, sessdata: Optional[str] = None, proxy: Optional[str] = None):
        """初始化提取器。
        
        Args:
            sessdata: B站登录凭证
            proxy: 代理服务器地址
        """
        self.sessdata = sessdata
        self.proxy = proxy
        self.signer = BiliWbiSign()
        
        # 设置请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com",
        }
        if sessdata:
            self.headers["Cookie"] = f"SESSDATA={sessdata}"
            
        # 设置代理
        self.proxies = {"http": proxy, "https": proxy} if proxy else None
        
    def extract_info(self, url: str) -> Dict[str, Any]:
        """提取视频信息。
        
        Args:
            url: B站视频URL
            
        Returns:
            Dict[str, Any]: 视频信息字典
            
        Raises:
            BiliBiliError: API调用出错
            NetworkError: 网络请求失败
            ParsingError: 解析失败
        """
        try:
            # 解析URL类型
            if 'bangumi/play' in url:
                return self._extract_bangumi_info(url)
            else:
                return self._extract_video_info(url)
                
        except requests.RequestException as e:
            logger.error(f"网络请求失败: {e}")
            raise NetworkError(f"网络请求失败: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            raise ParsingError(f"返回数据格式错误: {e}")
        except BiliBiliError:
            raise
        except Exception as e:
            logger.error(f"提取视频信息失败: {e}")
            raise BiliBiliError(f"提取视频信息失败: {e}")
            
    def _extract_video_info(self, url: str) -> Dict[str, Any]:
        """提取普通视频信息。
        
        Args:
            url: 视频URL
            
        Returns:
            Dict[str, Any]: 视频信息
        """
        # 从URL提取BV号
        bvid = self._extract_bvid(url)
        if not bvid:
            raise ParsingError(f"无效的视频URL: {url}")
            
        # 获取视频基本信息
        info = self._get_video_info(bvid)
        
        # 获取播放地址
        play_info = self._get_play_info(info["bvid"], info["cid"])
        
        # 合并信息
        info.update({
            "play_info": play_info,
            "qualities": self._extract_qualities(play_info)
        })
        
        return info
        
    def _extract_bangumi_info(self, url: str) -> Dict[str, Any]:
        """提取番剧信息。
        
        Args:
            url: 番剧URL
            
        Returns:
            Dict[str, Any]: 番剧信息
        """
        # 从URL提取season_id
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        
        if 'ss' in url:
            season_id = re.search(r'ss(\d+)', url).group(1)
        elif 'ep_id' in query:
            season_id = query['ep_id'][0]
        else:
            raise ParsingError(f"无效的番剧URL: {url}")
            
        # 获取番剧信息
        info = self._get_bangumi_info(season_id)
        
        # 获取播放地址
        play_info = self._get_play_info(info["episode_id"], info["cid"])
        
        # 合并信息
        info.update({
            "play_info": play_info,
            "qualities": self._extract_qualities(play_info)
        })
        
        return info
        
    def _extract_bvid(self, url: str) -> Optional[str]:
        """从URL中提取BV号。
        
        Args:
            url: 视频URL
            
        Returns:
            Optional[str]: BV号，无效URL返回None
        """
        pattern = r"BV[0-9A-Za-z]{10}"
        match = re.search(pattern, url)
        return match.group() if match else None
        
    def _get_video_info(self, bvid: str) -> Dict[str, Any]:
        """获取视频基本信息。
        
        Args:
            bvid: BV号
            
        Returns:
            Dict[str, Any]: 视频基本信息
        """
        # 准备参数
        params = {"bvid": bvid}
        
        # 添加WBI签名
        params = self.signer.sign(params)
        
        # 发送请求
        data = self._make_api_request(self.API_VIDEO_INFO, params)
        
        return self._parse_response(data)
        
    def _get_play_info(self, bvid: str, cid: str) -> Dict[str, Any]:
        """获取视频播放信息。
        
        Args:
            bvid: BV号
            cid: 分P ID
            
        Returns:
            Dict[str, Any]: 播放信息
        """
        # 准备参数
        params = {
            "bvid": bvid,
            "cid": cid,
            "qn": 127,  # 请求最高画质
            "fnval": 4048  # 启用所有编码格式
        }
        
        # 添加WBI签名
        params = self.signer.sign(params)
        
        # 发送请求
        data = self._make_api_request(self.API_PLAYURL, params)
        
        return self._parse_response(data)
        
    def _get_bangumi_info(self, season_id: str) -> Dict[str, Any]:
        """获取番剧信息。
        
        Args:
            season_id: 番剧ID
            
        Returns:
            Dict[str, Any]: 番剧信息
        """
        # 准备参数
        params = {"season_id": season_id}
        
        # 添加WBI签名
        params = self.signer.sign(params)
        
        # 发送请求
        data = self._make_api_request(self.API_BANGUMI_INFO, params)
        
        return self._parse_response(data)
        
    def _make_api_request(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """发送API请求。
        
        Args:
            url: API地址
            params: 请求参数
            
        Returns:
            Dict[str, Any]: API响应数据
            
        Raises:
            NetworkError: 网络请求失败
            BiliBiliError: API调用出错
        """
        try:
            # 发送请求
            resp = requests.get(
                url,
                params=params,
                headers=self.headers,
                proxies=self.proxies,
                timeout=10
            )
            resp.raise_for_status()
            
            # 解析响应
            data = resp.json()
            
            # 检查错误码
            if data["code"] != 0:
                error_class, message = self.ERROR_CODE_MAP.get(
                    data["code"],
                    (BiliBiliError, data["message"])
                )
                raise error_class(f"API调用失败: {message}")
                
            return data["data"]
            
        except requests.RequestException as e:
            logger.error(f"请求失败: {e}")
            raise NetworkError(f"请求失败: {e}")
            
    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析API响应。
        
        Args:
            data: API响应数据
            
        Returns:
            Dict[str, Any]: 解析后的数据
            
        Raises:
            ParsingError: 解析失败
        """
        try:
            if "dash" in data:
                return self._parse_new_response(data)
            else:
                return self._parse_legacy_response(data)
        except Exception as e:
            logger.error(f"解析响应失败: {e}")
            raise ParsingError(f"解析响应失败: {e}")
            
    def _parse_legacy_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析旧版API响应。
        
        Args:
            data: API响应数据
            
        Returns:
            Dict[str, Any]: 解析后的数据
        """
        return {
            "title": data.get("title", ""),
            "description": data.get("desc", ""),
            "duration": data.get("duration", 0),
            "owner": data.get("owner", {}).get("name", ""),
            "bvid": data.get("bvid", ""),
            "aid": data.get("aid", 0),
            "cid": data.get("cid", 0),
            "videos": data.get("videos", []),
            "quality": data.get("quality", 0),
            "format": "flv",
            "urls": data.get("durl", [])
        }
        
    def _parse_new_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析新版API响应。
        
        Args:
            data: API响应数据
            
        Returns:
            Dict[str, Any]: 解析后的数据
        """
        return {
            "title": data.get("title", ""),
            "description": data.get("desc", ""),
            "duration": data.get("duration", 0),
            "owner": data.get("owner", {}).get("name", ""),
            "bvid": data.get("bvid", ""),
            "aid": data.get("aid", 0),
            "cid": data.get("cid", 0),
            "videos": data.get("videos", []),
            "quality": data.get("quality", 0),
            "format": "dash",
            "dash": data.get("dash", {})
        }
        
    def _extract_qualities(self, play_info: Dict[str, Any]) -> Dict[int, str]:
        """提取可用画质列表。
        
        Args:
            play_info: 播放信息
            
        Returns:
            Dict[int, str]: 画质ID到描述的映射
        """
        qualities = {}
        
        # 从dash格式提取
        if "dash" in play_info:
            for video in play_info["dash"].get("video", []):
                qn = video.get("id", 0)
                qualities[qn] = self.QUALITY_MAP.get(qn, f"{qn}P")
                
        # 从flv格式提取
        elif "accept_quality" in play_info:
            for qn in play_info["accept_quality"]:
                qualities[qn] = self.QUALITY_MAP.get(qn, f"{qn}P")
                
        return qualities 