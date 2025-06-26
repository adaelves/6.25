"""哔哩哔哩签名模块。

提供WBI密钥获取和缓存功能。
"""

import os
import json
import time
import logging
from typing import Dict, Optional, Any
from pathlib import Path
import requests
import hashlib
import urllib.parse

logger = logging.getLogger(__name__)

class WBIKeyManager:
    """WBI密钥管理器。
    
    负责获取、缓存和使用WBI密钥。
    
    Attributes:
        cache_file: Path, 缓存文件路径
        cache_ttl: int, 缓存有效期（秒）
        _cached_keys: Optional[Dict[str, str]], 缓存的密钥
        _cache_timestamp: float, 缓存时间戳
    """
    
    # 备用密钥，当API请求失败时使用
    _FALLBACK_IMG_KEY = "7cd084941338484aae1ad9425b84077c"
    _FALLBACK_SUB_KEY = "4932caff0ff746eab6f01bf08b70ac45"
    
    def __init__(
        self,
        cache_dir: str = ".cache",
        cache_ttl: int = 3600  # 1小时
    ):
        """初始化密钥管理器。
        
        Args:
            cache_dir: 缓存目录
            cache_ttl: 缓存有效期（秒）
        """
        self.cache_file = Path(cache_dir) / "wbi_keys.json"
        self.cache_ttl = cache_ttl
        self._cached_keys = None
        self._cache_timestamp = 0
        
        # 创建缓存目录
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        
    def _fetch_wbi_keys(self) -> Dict[str, str]:
        """从API获取WBI密钥。
        
        Returns:
            Dict[str, str]: 包含img_key和sub_key的字典
            
        Raises:
            requests.RequestException: 请求失败
            ValueError: 响应格式错误
        """
        try:
            resp = requests.get(
                "https://api.bilibili.com/x/web-interface/nav",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10  # 10秒超时
            )
            resp.raise_for_status()
            
            data = resp.json()
            if not data.get("code") == 0:
                raise ValueError(f"API返回错误: {data.get('message')}")
                
            wbi_img = data.get("data", {}).get("wbi_img", {})
            img_key = wbi_img.get("key")
            sub_key = wbi_img.get("sub_key")
            
            if not (img_key and sub_key):
                raise ValueError("未找到WBI密钥")
                
            return {
                "img_key": img_key,
                "sub_key": sub_key
            }
            
        except requests.RequestException as e:
            logger.error(f"获取WBI密钥失败: {e}")
            raise
            
    def _load_cached_keys(self) -> Optional[Dict[str, str]]:
        """从缓存文件加载密钥。
        
        Returns:
            Optional[Dict[str, str]]: 缓存的密钥，如果缓存无效则返回None
        """
        try:
            if not self.cache_file.exists():
                return None
                
            with open(self.cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                
            # 检查缓存是否过期
            if time.time() - cache_data.get("timestamp", 0) > self.cache_ttl:
                return None
                
            keys = cache_data.get("keys")
            if not (keys and "img_key" in keys and "sub_key" in keys):
                return None
                
            return keys
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"读取缓存密钥失败: {e}")
            return None
            
    def _save_keys_to_cache(self, keys: Dict[str, str]) -> None:
        """保存密钥到缓存文件。
        
        Args:
            keys: 要缓存的密钥
        """
        try:
            cache_data = {
                "timestamp": time.time(),
                "keys": keys
            }
            
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2)
                
        except (IOError, OSError) as e:
            logger.warning(f"保存密钥到缓存失败: {e}")
            
    def get_keys(self, use_cache: bool = True) -> Dict[str, str]:
        """获取WBI密钥。
        
        Args:
            use_cache: 是否使用缓存
            
        Returns:
            Dict[str, str]: 包含img_key和sub_key的字典
            
        Raises:
            RuntimeError: 获取密钥失败且无可用缓存
        """
        # 尝试从缓存加载
        if use_cache:
            cached_keys = self._load_cached_keys()
            if cached_keys:
                logger.debug("使用缓存的WBI密钥")
                return cached_keys
                
        try:
            # 从API获取新密钥
            keys = self._fetch_wbi_keys()
            logger.debug("成功获取新的WBI密钥")
            
            # 保存到缓存
            self._save_keys_to_cache(keys)
            
            return keys
            
        except Exception as e:
            logger.error(f"获取WBI密钥失败: {e}")
            
            # 如果允许使用缓存，再次尝试加载（即使过期）
            if use_cache:
                try:
                    with open(self.cache_file, "r", encoding="utf-8") as f:
                        cache_data = json.load(f)
                    keys = cache_data.get("keys")
                    if keys:
                        logger.warning("使用过期的缓存密钥")
                        return keys
                except Exception:
                    pass
                    
            # 使用备用密钥
            logger.warning("使用备用WBI密钥")
            return {
                "img_key": self._FALLBACK_IMG_KEY,
                "sub_key": self._FALLBACK_SUB_KEY
            }
            
    def sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """使用WBI密钥对参数进行签名。
        
        Args:
            params: 要签名的参数字典
            
        Returns:
            Dict[str, Any]: 包含签名的参数字典
            
        Raises:
            ValueError: 参数无效
        """
        if not isinstance(params, dict):
            raise ValueError("参数必须是字典类型")
            
        # 获取密钥
        keys = self.get_keys()
        img_key = keys["img_key"]
        sub_key = keys["sub_key"]
        
        # 添加时间戳
        params = params.copy()
        params["wts"] = str(int(time.time()))
        
        # 按照key排序
        sorted_params = dict(sorted(params.items()))
        
        # 拼接参数
        query = urllib.parse.urlencode(sorted_params)
        
        # 计算签名
        wbi_key = img_key + sub_key
        hash_value = hashlib.md5((query + wbi_key).encode()).hexdigest()
        
        # 添加签名
        params["w_rid"] = hash_value
        
        return params 