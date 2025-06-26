"""B站 API 签名模块。

提供 WBI 签名生成功能。
支持自动获取和更新密钥。
"""

import time
import json
import logging
import hashlib
from typing import Dict, Tuple, Optional
from pathlib import Path
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class BiliWbiSign:
    """B站 WBI 签名生成器。
    
    支持自动获取和缓存 WBI 密钥。
    支持定时更新密钥。
    
    Attributes:
        _img_key: str, 图片密钥
        _sub_key: str, 子密钥
        _key_update_time: float, 密钥更新时间戳
        _key_ttl: int, 密钥有效期（秒）
        _cache_file: Path, 密钥缓存文件路径
    """
    
    def __init__(
        self,
        key_ttl: int = 3600,
        cache_file: Optional[Path] = None,
        proxy: Optional[str] = None
    ):
        """初始化签名生成器。
        
        Args:
            key_ttl: 密钥有效期（秒）
            cache_file: 密钥缓存文件路径
            proxy: 代理服务器
        """
        self._img_key = ""
        self._sub_key = ""
        self._key_update_time = 0
        self._key_ttl = key_ttl
        self._cache_file = cache_file or Path.home() / ".bilibili_wbi_keys"
        self._proxy = proxy
        
        # 尝试加载缓存的密钥
        self._load_cached_keys()
        
    def fetch_wbi_keys(self) -> Tuple[str, str]:
        """获取 WBI 密钥。
        
        从 B 站 API 获取最新的 WBI 密钥。
        
        Returns:
            Tuple[str, str]: (img_key, sub_key)
            
        Raises:
            requests.RequestException: 请求失败
            ValueError: 响应格式错误
        """
        try:
            # 准备代理
            proxies = {"http": self._proxy, "https": self._proxy} if self._proxy else None
            
            # 发送请求
            resp = requests.get(
                "https://api.bilibili.com/x/web-interface/nav",
                proxies=proxies,
                timeout=10
            )
            resp.raise_for_status()
            
            # 解析响应
            data = resp.json()
            if data["code"] != 0:
                raise ValueError(f"API错误: {data['message']}")
                
            img_key = data["data"]["wbi_img"]["img_url"].split("/")[-1].split(".")[0]
            sub_key = data["data"]["wbi_img"]["sub_url"].split("/")[-1].split(".")[0]
            
            logger.info("成功获取 WBI 密钥")
            return img_key, sub_key
            
        except Exception as e:
            logger.error(f"获取 WBI 密钥失败: {e}")
            raise
            
    def _load_cached_keys(self) -> None:
        """加载缓存的密钥。"""
        try:
            if self._cache_file.exists():
                with open(self._cache_file) as f:
                    data = json.load(f)
                    
                # 检查密钥是否过期
                if time.time() - data["timestamp"] < self._key_ttl:
                    self._img_key = data["img_key"]
                    self._sub_key = data["sub_key"]
                    self._key_update_time = data["timestamp"]
                    logger.info("已加载缓存的 WBI 密钥")
                    return
                    
        except Exception as e:
            logger.warning(f"加载缓存的密钥失败: {e}")
            
    def _save_keys(self) -> None:
        """保存密钥到缓存文件。"""
        try:
            data = {
                "img_key": self._img_key,
                "sub_key": self._sub_key,
                "timestamp": self._key_update_time
            }
            with open(self._cache_file, "w") as f:
                json.dump(data, f)
            logger.info(f"已保存 WBI 密钥到: {self._cache_file}")
        except Exception as e:
            logger.warning(f"保存密钥失败: {e}")
            
    def _update_keys_if_needed(self) -> None:
        """如果需要则更新密钥。"""
        now = time.time()
        if not self._img_key or now - self._key_update_time >= self._key_ttl:
            self._img_key, self._sub_key = self.fetch_wbi_keys()
            self._key_update_time = now
            self._save_keys()
            
    def sign(self, params: Dict[str, str]) -> Dict[str, str]:
        """生成带签名的参数。
        
        Args:
            params: 原始参数字典
            
        Returns:
            Dict[str, str]: 带签名的参数字典
            
        Raises:
            ValueError: 参数错误
        """
        try:
            # 更新密钥
            self._update_keys_if_needed()
            
            # 准备签名参数
            wts = str(int(time.time()))
            params["wts"] = wts
            
            # 混合密钥
            mixed_key = self._img_key + self._sub_key
            
            # 按键名排序
            sorted_params = sorted(params.items())
            
            # 构造签名字符串
            query = "&".join(f"{k}={v}" for k, v in sorted_params)
            
            # 计算签名
            sign = hashlib.md5(
                (query + mixed_key).encode()
            ).hexdigest()
            
            # 添加签名
            params["w_rid"] = sign
            
            return params
            
        except Exception as e:
            logger.error(f"生成签名失败: {e}")
            raise ValueError(f"生成签名失败: {e}")

# 创建全局实例
bili_sign = BiliWbiSign()

def sign_params(params: Dict[str, str]) -> Dict[str, str]:
    """便捷函数：生成带签名的参数。
    
    Args:
        params: 原始参数字典
        
    Returns:
        Dict[str, str]: 带签名的参数字典
    """
    return bili_sign.sign(params) 