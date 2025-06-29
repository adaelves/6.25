"""Cookie 管理器模块。

提供 cookie 的保存、加载和管理功能。
"""

import os
import json
import logging
import pickle
from pathlib import Path
from typing import Dict, Optional, Any
from http.cookiejar import CookieJar, MozillaCookieJar

import requests
import browser_cookie3

logger = logging.getLogger(__name__)

class CookieManager:
    """Cookie 管理器。
    
    支持以下功能：
    1. 从浏览器导入 cookie
    2. 从文件加载 cookie
    3. 保存 cookie 到文件
    4. 为不同平台管理 cookie
    5. 自动更新过期 cookie
    """
    
    def __init__(self, cookie_dir: str = "./cookies"):
        """初始化 Cookie 管理器。
        
        Args:
            cookie_dir: cookie 保存目录，默认为"./cookies"
        """
        self.cookie_dir = Path(cookie_dir)
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        
        # 平台 cookie 字典
        self.cookies: Dict[str, CookieJar] = {}
        
    def load_cookies(self, platform: str) -> Optional[CookieJar]:
        """加载平台的 cookie。
        
        Args:
            platform: 平台名称
            
        Returns:
            Optional[CookieJar]: cookie jar 对象，如果不存在则返回 None
        """
        # 如果已加载则直接返回
        if platform in self.cookies:
            return self.cookies[platform]
            
        # 尝试从文件加载
        cookie_file = self.cookie_dir / f"{platform}.cookies"
        if cookie_file.exists():
            try:
                jar = MozillaCookieJar(str(cookie_file))
                jar.load()
                self.cookies[platform] = jar
                return jar
            except Exception as e:
                logger.error(f"加载 cookie 文件失败: {e}")
                
        return None
        
    def save_cookies(self, platform: str, cookies: CookieJar) -> bool:
        """保存平台的 cookie。
        
        Args:
            platform: 平台名称
            cookies: cookie jar 对象
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 保存到文件
            cookie_file = self.cookie_dir / f"{platform}.cookies"
            if isinstance(cookies, MozillaCookieJar):
                cookies.save()
            else:
                jar = MozillaCookieJar(str(cookie_file))
                for cookie in cookies:
                    jar.set_cookie(cookie)
                jar.save()
                
            # 更新缓存
            self.cookies[platform] = cookies
            return True
            
        except Exception as e:
            logger.error(f"保存 cookie 失败: {e}")
            return False
            
    def import_from_browser(
        self,
        platform: str,
        domain: str,
        browser: str = "chrome"
    ) -> bool:
        """从浏览器导入 cookie。
        
        Args:
            platform: 平台名称
            domain: cookie 域名
            browser: 浏览器名称，可选值：'chrome'、'firefox'、'edge'等
            
        Returns:
            bool: 是否导入成功
        """
        try:
            # 获取浏览器 cookie
            if browser == "chrome":
                cookies = browser_cookie3.chrome(domain_name=domain)
            elif browser == "firefox":
                cookies = browser_cookie3.firefox(domain_name=domain)
            elif browser == "edge":
                cookies = browser_cookie3.edge(domain_name=domain)
            else:
                logger.error(f"不支持的浏览器类型: {browser}")
                return False
                
            # 保存 cookie
            return self.save_cookies(platform, cookies)
            
        except Exception as e:
            logger.error(f"从浏览器导入 cookie 失败: {e}")
            return False
            
    def get_cookies(self, platform: str) -> Dict[str, str]:
        """获取平台的 cookie 字典。
        
        Args:
            platform: 平台名称
            
        Returns:
            Dict[str, str]: cookie 字典
        """
        cookies = {}
        jar = self.load_cookies(platform)
        
        if jar:
            for cookie in jar:
                cookies[cookie.name] = cookie.value
                
        return cookies
        
    def set_cookies(
        self,
        platform: str,
        cookies: Dict[str, Any]
    ) -> bool:
        """设置平台的 cookie。
        
        Args:
            platform: 平台名称
            cookies: cookie 字典
            
        Returns:
            bool: 是否设置成功
        """
        try:
            # 创建 cookie jar
            jar = MozillaCookieJar()
            
            # 添加 cookie
            for name, value in cookies.items():
                jar.set_cookie(
                    requests.cookies.create_cookie(
                        name=name,
                        value=str(value)
                    )
                )
                
            # 保存 cookie
            return self.save_cookies(platform, jar)
            
        except Exception as e:
            logger.error(f"设置 cookie 失败: {e}")
            return False
            
    def clear_cookies(self, platform: str) -> bool:
        """清除平台的 cookie。
        
        Args:
            platform: 平台名称
            
        Returns:
            bool: 是否清除成功
        """
        try:
            # 删除文件
            cookie_file = self.cookie_dir / f"{platform}.cookies"
            if cookie_file.exists():
                cookie_file.unlink()
                
            # 清除缓存
            if platform in self.cookies:
                del self.cookies[platform]
                
            return True
            
        except Exception as e:
            logger.error(f"清除 cookie 失败: {e}")
            return False
            
    def clear_all_cookies(self) -> bool:
        """清除所有平台的 cookie。
        
        Returns:
            bool: 是否清除成功
        """
        try:
            # 删除所有文件
            for file in self.cookie_dir.glob("*.cookies"):
                file.unlink()
                
            # 清除缓存
            self.cookies.clear()
            
            return True
            
        except Exception as e:
            logger.error(f"清除所有 cookie 失败: {e}")
            return False 