"""认证管理。

提供跨平台认证管理功能。
"""

import logging
import json
import os
import time
from typing import Dict, Optional, List
from pathlib import Path
from datetime import datetime, timedelta
import keyring
import browser_cookie3
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options

from ..exceptions import AuthError
from ..utils.network import NetworkSession

logger = logging.getLogger(__name__)

class AuthManager:
    """认证管理器。
    
    提供以下功能：
    1. 多平台认证管理
    2. Cookie同步
    3. 令牌管理
    4. 自动登录
    5. 安全存储
    
    Attributes:
        auth_dir: 认证目录
        browser: 浏览器实例
        network: 网络会话
    """
    
    # 支持的平台
    PLATFORMS = {
        'twitter': {
            'auth_url': 'https://twitter.com/login',
            'cookie_domain': '.twitter.com',
            'token_key': 'auth_token',
            'required_cookies': ['auth_token', 'ct0']
        },
        'instagram': {
            'auth_url': 'https://www.instagram.com/accounts/login',
            'cookie_domain': '.instagram.com',
            'token_key': 'sessionid',
            'required_cookies': ['sessionid', 'ds_user_id']
        },
        'youtube': {
            'auth_url': 'https://accounts.google.com/signin',
            'cookie_domain': '.youtube.com',
            'token_key': 'SAPISID',
            'required_cookies': ['SAPISID', 'APISID', 'SSID']
        },
        'tiktok': {
            'auth_url': 'https://www.tiktok.com/login',
            'cookie_domain': '.tiktok.com',
            'token_key': 'sessionid',
            'required_cookies': ['sessionid', 'tt_webid']
        }
    }
    
    def __init__(
        self,
        auth_dir: str = './auth',
        headless: bool = True
    ):
        """初始化管理器。
        
        Args:
            auth_dir: 认证目录，默认'./auth'
            headless: 是否无头模式，默认True
        """
        self.auth_dir = Path(auth_dir)
        self.auth_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化浏览器
        options = Options()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        self.browser = Chrome(options=options)
        self.network = NetworkSession()
        
    def login(
        self,
        platform: str,
        username: str,
        password: str
    ) -> bool:
        """登录平台。
        
        Args:
            platform: 平台名称
            username: 用户名
            password: 密码
            
        Returns:
            bool: 是否成功
            
        Raises:
            AuthError: 认证失败
        """
        try:
            if platform not in self.PLATFORMS:
                raise AuthError(f"Unsupported platform: {platform}")
                
            # 获取平台配置
            config = self.PLATFORMS[platform]
            
            # 访问登录页
            self.browser.get(config['auth_url'])
            
            # 等待登录完成
            self._wait_for_login(platform)
            
            # 保存认证信息
            self._save_auth(platform, username)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to login {platform}: {e}")
            raise AuthError(f"Failed to login {platform}: {e}")
            
    def sync_cookies_across_platforms(
        self,
        platforms: Optional[List[str]] = None
    ):
        """同步多平台认证状态。
        
        Args:
            platforms: 平台列表，可选
            
        Raises:
            AuthError: 同步失败
        """
        try:
            # 获取需要同步的平台
            platforms = platforms or list(self.PLATFORMS.keys())
            
            for platform in platforms:
                if platform not in self.PLATFORMS:
                    logger.warning(f"Skipping unsupported platform: {platform}")
                    continue
                    
                # 导出浏览器Cookie
                cookies = self._export_cookies(platform)
                if not cookies:
                    logger.warning(f"No cookies found for {platform}")
                    continue
                    
                # 保存Cookie
                cookie_path = self._get_cookie_path(platform)
                with cookie_path.open('w') as f:
                    json.dump(cookies, f)
                    
                # 导入到网络会话
                self._import_cookies(platform, cookies)
                
                logger.info(f"Synced cookies for {platform}")
                
        except Exception as e:
            logger.error(f"Failed to sync cookies: {e}")
            raise AuthError(f"Failed to sync cookies: {e}")
            
    def check_auth(self, platform: str) -> bool:
        """检查认证状态。
        
        Args:
            platform: 平台名称
            
        Returns:
            bool: 是否已认证
        """
        try:
            if platform not in self.PLATFORMS:
                return False
                
            # 获取平台配置
            config = self.PLATFORMS[platform]
            
            # 检查Cookie
            cookies = self._export_cookies(platform)
            if not cookies:
                return False
                
            # 检查必需的Cookie
            required = set(config['required_cookies'])
            existing = {c['name'] for c in cookies}
            
            return required.issubset(existing)
            
        except Exception as e:
            logger.error(f"Failed to check auth: {e}")
            return False
            
    def clear_auth(self, platform: str):
        """清除认证信息。
        
        Args:
            platform: 平台名称
            
        Raises:
            AuthError: 清除失败
        """
        try:
            if platform not in self.PLATFORMS:
                raise AuthError(f"Unsupported platform: {platform}")
                
            # 清除Cookie文件
            cookie_path = self._get_cookie_path(platform)
            if cookie_path.exists():
                cookie_path.unlink()
                
            # 清除浏览器Cookie
            self.browser.delete_all_cookies()
            
            # 清除密钥库
            keyring.delete_password(
                'social_downloader',
                f'{platform}_token'
            )
            
        except Exception as e:
            logger.error(f"Failed to clear auth: {e}")
            raise AuthError(f"Failed to clear auth: {e}")
            
    def _export_cookies(self, platform: str) -> List[Dict]:
        """导出Cookie。
        
        Args:
            platform: 平台名称
            
        Returns:
            List[Dict]: Cookie列表
        """
        try:
            # 获取平台配置
            config = self.PLATFORMS[platform]
            
            # 获取浏览器Cookie
            cookies = []
            for cookie in self.browser.get_cookies():
                if config['cookie_domain'] in cookie['domain']:
                    cookies.append(cookie)
                    
            return cookies
            
        except Exception as e:
            logger.error(f"Failed to export cookies: {e}")
            return []
            
    def _import_cookies(
        self,
        platform: str,
        cookies: List[Dict]
    ):
        """导入Cookie。
        
        Args:
            platform: 平台名称
            cookies: Cookie列表
        """
        try:
            # 获取平台配置
            config = self.PLATFORMS[platform]
            
            # 设置Cookie
            for cookie in cookies:
                if config['cookie_domain'] in cookie['domain']:
                    self.network.session.cookies.set(**cookie)
                    
        except Exception as e:
            logger.error(f"Failed to import cookies: {e}")
            
    def _save_auth(self, platform: str, username: str):
        """保存认证信息。
        
        Args:
            platform: 平台名称
            username: 用户名
        """
        try:
            # 获取平台配置
            config = self.PLATFORMS[platform]
            
            # 获取认证令牌
            cookies = self._export_cookies(platform)
            for cookie in cookies:
                if cookie['name'] == config['token_key']:
                    # 保存到密钥库
                    keyring.set_password(
                        'social_downloader',
                        f'{platform}_token',
                        cookie['value']
                    )
                    break
                    
            # 保存用户信息
            user_path = self.auth_dir / f'{platform}_user.json'
            with user_path.open('w') as f:
                json.dump({
                    'username': username,
                    'updated_at': time.time()
                }, f)
                
        except Exception as e:
            logger.error(f"Failed to save auth: {e}")
            
    def _wait_for_login(self, platform: str, timeout: int = 60):
        """等待登录完成。
        
        Args:
            platform: 平台名称
            timeout: 超时时间(秒)，默认60秒
            
        Raises:
            AuthError: 超时
        """
        try:
            # 获取平台配置
            config = self.PLATFORMS[platform]
            
            # 等待必需的Cookie
            start_time = time.time()
            while time.time() - start_time < timeout:
                cookies = self._export_cookies(platform)
                if not cookies:
                    time.sleep(1)
                    continue
                    
                # 检查必需的Cookie
                required = set(config['required_cookies'])
                existing = {c['name'] for c in cookies}
                
                if required.issubset(existing):
                    return
                    
                time.sleep(1)
                
            raise AuthError("Login timeout")
            
        except Exception as e:
            logger.error(f"Failed to wait for login: {e}")
            raise AuthError(f"Failed to wait for login: {e}")
            
    def _get_cookie_path(self, platform: str) -> Path:
        """获取Cookie文件路径。
        
        Args:
            platform: 平台名称
            
        Returns:
            Path: 文件路径
        """
        return self.auth_dir / f'{platform}_cookies.json'
        
    def __del__(self):
        """清理资源。"""
        try:
            self.browser.quit()
        except Exception as e:
            logger.warning(f"Failed to quit browser: {e}") 