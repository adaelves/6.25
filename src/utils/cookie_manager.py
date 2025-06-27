"""Cookie管理模块。

提供统一的Cookie管理功能，支持：
- 自动从配置目录加载平台专属Cookie
- 支持通用Cookie继承
- 提供多种格式转换方法
- 支持Cookie的保存和更新
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Union, Any

logger = logging.getLogger(__name__)

class CookieManager:
    """Cookie管理器。
    
    提供统一的Cookie管理功能，支持多平台和通用Cookie。
    
    Attributes:
        cookie_dir: Cookie配置目录
        _cache: Cookie缓存字典
    """
    
    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        """初始化Cookie管理器。
        
        Args:
            config_dir: 配置目录路径，默认为'config'
        """
        base_dir = Path(config_dir) if config_dir else Path("config")
        self.cookie_dir = base_dir / "cookies"
        self._cache: Dict[str, Dict[str, str]] = {}
        
        # 确保目录存在
        self._ensure_dirs()
        
    def _ensure_dirs(self) -> None:
        """确保必要的目录结构存在。"""
        try:
            self.cookie_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Cookie目录已确认: {self.cookie_dir}")
        except Exception as e:
            logger.error(f"创建Cookie目录失败: {e}")
            raise
            
    def _load_json_file(self, file_path: Path) -> Dict[str, str]:
        """加载JSON文件。
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            Dict[str, str]: 加载的数据
            
        Raises:
            ValueError: JSON格式无效
        """
        try:
            if file_path.exists():
                data = json.loads(file_path.read_text(encoding='utf-8'))
                if not isinstance(data, dict):
                    raise ValueError(f"无效的Cookie格式: {file_path}")
                return {str(k): str(v) for k, v in data.items()}
            return {}
        except Exception as e:
            logger.error(f"加载Cookie文件失败 {file_path}: {e}")
            return {}
            
    def get_cookies(self, platform: str, use_cache: bool = True) -> Dict[str, str]:
        """获取指定平台的Cookie。
        
        优先加载平台专属Cookie，然后与通用Cookie合并。
        
        Args:
            platform: 平台标识（如'twitter'、'youtube'等）
            use_cache: 是否使用缓存
            
        Returns:
            Dict[str, str]: Cookie字典
        """
        # 检查缓存
        if use_cache and platform in self._cache:
            return self._cache[platform].copy()
            
        # 构建文件路径
        platform_file = self.cookie_dir / f"{platform}.json"
        universal_file = self.cookie_dir / "universal.json"
        
        # 加载Cookie
        cookies = self._load_json_file(universal_file)  # 先加载通用Cookie
        cookies.update(self._load_json_file(platform_file))  # 再覆盖平台专属Cookie
        
        # 更新缓存
        self._cache[platform] = cookies.copy()
        
        return cookies
        
    def save_cookies(
        self,
        platform: str,
        cookies: Dict[str, Any],
        merge: bool = True
    ) -> bool:
        """保存Cookie到文件。
        
        Args:
            platform: 平台标识
            cookies: Cookie字典
            merge: 是否与现有Cookie合并
            
        Returns:
            bool: 是否保存成功
        """
        try:
            file_path = self.cookie_dir / f"{platform}.json"
            
            # 处理现有数据
            if merge and file_path.exists():
                existing = self._load_json_file(file_path)
                existing.update(cookies)
                cookies = existing
                
            # 确保所有值都是字符串
            cookies = {str(k): str(v) for k, v in cookies.items()}
            
            # 保存到文件
            file_path.write_text(
                json.dumps(cookies, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            
            # 更新缓存
            self._cache[platform] = cookies.copy()
            
            logger.debug(f"Cookie已保存: {platform}")
            return True
            
        except Exception as e:
            logger.error(f"保存Cookie失败 {platform}: {e}")
            return False
            
    def to_header(self, platform: str) -> str:
        """转换为HTTP Cookie头部格式。
        
        Args:
            platform: 平台标识
            
        Returns:
            str: Cookie头部字符串
        """
        cookies = self.get_cookies(platform)
        return "; ".join(f"{k}={v}" for k, v in cookies.items())
        
    def parse_header(self, header: str) -> Dict[str, str]:
        """从HTTP Cookie头部解析。
        
        Args:
            header: Cookie头部字符串
            
        Returns:
            Dict[str, str]: Cookie字典
        """
        cookies = {}
        if not header:
            return cookies
            
        for item in header.split(";"):
            if "=" in item:
                key, value = item.strip().split("=", 1)
                cookies[key.strip()] = value.strip()
                
        return cookies
        
    def clear_cache(self, platform: Optional[str] = None) -> None:
        """清除缓存。
        
        Args:
            platform: 平台标识，如果为None则清除所有缓存
        """
        if platform:
            self._cache.pop(platform, None)
        else:
            self._cache.clear()
            
    def delete_cookies(self, platform: str) -> bool:
        """删除指定平台的Cookie文件。
        
        Args:
            platform: 平台标识
            
        Returns:
            bool: 是否删除成功
        """
        try:
            file_path = self.cookie_dir / f"{platform}.json"
            if file_path.exists():
                file_path.unlink()
                self.clear_cache(platform)
                logger.debug(f"Cookie已删除: {platform}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除Cookie失败 {platform}: {e}")
            return False

    def has_cookies(self, platform: Optional[str] = None) -> bool:
        """检查是否有Cookie。
        
        Args:
            platform: 平台标识，如果为None则检查是否有任何Cookie
            
        Returns:
            bool: 是否有Cookie
        """
        if platform:
            cookies = self.get_cookies(platform)
            return bool(cookies)
        else:
            # 检查是否有任何平台的Cookie
            for file in self.cookie_dir.glob("*.json"):
                if self._load_json_file(file):
                    return True
            return False

    def get_cookie_file(self, platform: str = "twitter") -> str:
        """获取Cookie文件路径。
        
        Args:
            platform: 平台标识
            
        Returns:
            str: Cookie文件路径
        """
        cookie_file = self.cookie_dir / f"{platform}.txt"
        
        # 如果文件不存在，创建一个空的Netscape格式的Cookie文件
        if not cookie_file.exists():
            cookie_file.write_text(
                "# Netscape HTTP Cookie File\n" +
                "# https://curl.haxx.se/rfc/cookie_spec.html\n" +
                "# This is a generated file!  Do not edit.\n\n",
                encoding='utf-8'
            )
            
        return str(cookie_file) 