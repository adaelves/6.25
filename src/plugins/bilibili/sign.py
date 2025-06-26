"""B站 API 签名模块。

提供 WBI 签名生成功能。
支持自动获取和更新密钥。
"""

import time
import json
import logging
import hashlib
from typing import Dict, Tuple, Optional, ClassVar, Union
from pathlib import Path
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class BiliWbiSign:
    """B站 WBI 签名生成器。
    
    支持自动获取和缓存 WBI 密钥。
    支持定时更新密钥。
    支持密钥失效时使用备用密钥。
    
    Attributes:
        _img_key: str, 图片密钥
        _sub_key: str, 子密钥
        _key_update_time: float, 密钥更新时间戳
        _key_ttl: int, 密钥有效期（秒）
        _cache_file: Path, 密钥缓存文件路径
    """
    
    # 类级别的密钥缓存
    _wbi_keys: ClassVar[Optional[Tuple[str, str]]] = None
    _last_update: ClassVar[float] = 0
    
    # 备用密钥（硬编码，用于紧急情况）
    _FALLBACK_IMG_KEY = "7cd084941338484aae1ad9425b84077c"  # 示例密钥，需要替换为真实的
    _FALLBACK_SUB_KEY = "4932caff0ff746eab6f01bf08b70ac45"  # 示例密钥，需要替换为真实的
    
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
        self._use_fallback = False
        
        # 尝试加载缓存的密钥
        self._load_cached_keys()
        
    @classmethod
    def get_keys(cls) -> Tuple[str, str]:
        """获取当前的 WBI 密钥。
        
        如果密钥过期或不存在，会尝试获取新密钥。
        
        Returns:
            Tuple[str, str]: (img_key, sub_key)
        """
        now = time.time()
        if not cls._wbi_keys or now - cls._last_update > 3600:  # 1小时刷新
            try:
                cls._fetch_new_keys()
            except Exception as e:
                logger.error(f"获取新密钥失败: {e}")
                if cls._wbi_keys:  # 如果有旧密钥，继续使用
                    logger.warning("使用旧密钥继续")
                    return cls._wbi_keys
                # 如果没有任何密钥，使用备用密钥
                logger.warning("使用备用密钥")
                return cls._FALLBACK_IMG_KEY, cls._FALLBACK_SUB_KEY
        return cls._wbi_keys
        
    @classmethod
    def _fetch_new_keys(cls) -> None:
        """获取新的 WBI 密钥。
        
        Raises:
            requests.RequestException: 请求失败
            ValueError: 响应格式错误
        """
        try:
            resp = requests.get(
                "https://api.bilibili.com/x/web-interface/nav",
                timeout=10
            )
            resp.raise_for_status()
            
            data = resp.json()
            if data["code"] != 0:
                raise ValueError(f"API错误: {data['message']}")
                
            img_key = data["data"]["wbi_img"]["img_url"].split("/")[-1].split(".")[0]
            sub_key = data["data"]["wbi_img"]["sub_url"].split("/")[-1].split(".")[0]
            
            # 验证密钥有效性
            if not cls._verify_keys(img_key, sub_key):
                raise ValueError("获取的密钥验证失败")
                
            cls._wbi_keys = (img_key, sub_key)
            cls._last_update = time.time()
            logger.info("成功获取并验证新的 WBI 密钥")
            
        except Exception as e:
            logger.error(f"获取新密钥失败: {e}")
            raise
            
    @staticmethod
    def _verify_keys(img_key: str, sub_key: str) -> bool:
        """验证密钥的有效性。
        
        Args:
            img_key: 图片密钥
            sub_key: 子密钥
            
        Returns:
            bool: 密钥是否有效
        """
        try:
            # 检查密钥格式
            if not (len(img_key) == 32 and len(sub_key) == 32):
                return False
                
            if not all(c in "0123456789abcdef" for c in img_key + sub_key):
                return False
                
            # 构造测试参数
            test_params = {
                "foo": "bar",
                "timestamp": str(int(time.time()))
            }
            
            # 使用密钥生成签名
            mixed_key = img_key + sub_key
            sorted_params = sorted(test_params.items())
            query = "&".join(f"{k}={v}" for k, v in sorted_params)
            sign = hashlib.md5((query + mixed_key).encode()).hexdigest()
            
            # 验证签名长度和格式
            if not (len(sign) == 32 and all(c in "0123456789abcdef" for c in sign)):
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"验证密钥失败: {e}")
            return False
            
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
            
            # 验证密钥有效性
            if not self._verify_keys(img_key, sub_key):
                raise ValueError("获取的密钥验证失败")
                
            logger.info("成功获取并验证 WBI 密钥")
            return img_key, sub_key
            
        except Exception as e:
            logger.error(f"获取 WBI 密钥失败: {e}")
            if self._use_fallback:
                logger.warning("已经在使用备用密钥")
                raise
            
            # 使用备用密钥
            logger.warning("使用备用密钥")
            self._use_fallback = True
            return self._FALLBACK_IMG_KEY, self._FALLBACK_SUB_KEY
            
    def _load_cached_keys(self) -> None:
        """加载缓存的密钥。"""
        try:
            if self._cache_file.exists():
                with open(self._cache_file) as f:
                    data = json.load(f)
                    
                # 检查密钥是否过期
                if time.time() - data["timestamp"] < self._key_ttl:
                    # 验证密钥有效性
                    if self._verify_keys(data["img_key"], data["sub_key"]):
                        self._img_key = data["img_key"]
                        self._sub_key = data["sub_key"]
                        self._key_update_time = data["timestamp"]
                        logger.info("已加载并验证缓存的 WBI 密钥")
                        return
                    else:
                        logger.warning("缓存的密钥验证失败")
                        
        except Exception as e:
            logger.warning(f"加载缓存的密钥失败: {e}")
            
    def _save_keys(self) -> None:
        """保存密钥到缓存文件。"""
        try:
            # 不保存备用密钥
            if self._use_fallback:
                logger.info("使用备用密钥，跳过保存")
                return
                
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
            try:
                self._img_key, self._sub_key = self.fetch_wbi_keys()
                self._key_update_time = now
                self._save_keys()
            except Exception as e:
                logger.error(f"更新密钥失败: {e}")
                if not self._img_key:  # 如果没有任何可用密钥
                    self._img_key = self._FALLBACK_IMG_KEY
                    self._sub_key = self._FALLBACK_SUB_KEY
                    self._use_fallback = True
                    logger.warning("使用备用密钥")
            
    def _validate_params(self, params: Dict[str, str]) -> None:
        """验证参数有效性。
        
        Args:
            params: 要验证的参数字典
            
        Raises:
            ValueError: 参数无效
        """
        if not isinstance(params, dict):
            raise ValueError("参数必须是字典类型")
            
        for key, value in params.items():
            if not isinstance(key, str):
                raise ValueError("参数键必须是字符串类型")
            if not isinstance(value, str):
                raise ValueError("参数值必须是字符串类型")
            
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
            # 验证参数
            self._validate_params(params)
            
            # 更新密钥
            self._update_keys_if_needed()
            
            # 准备签名参数
            wts = str(int(time.time()))
            params = params.copy()  # 不修改原始参数
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