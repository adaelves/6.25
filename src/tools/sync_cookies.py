"""Twitter Cookie 同步工具。

从各种浏览器同步 Twitter(X) Cookie 到配置文件。
支持的浏览器：
- Chrome
- Firefox
- Edge
- Brave
- Opera
- Vivaldi
- Chromium
- Cent Browser (基于Chromium)
"""

import os
import logging
from typing import Dict, List, Optional, Callable
from pathlib import Path
import json
import browser_cookie3
from http.cookiejar import Cookie
from datetime import datetime
import sqlite3
import base64
import win32crypt
from Crypto.Cipher import AES

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def get_chrome_encryption_key() -> Optional[bytes]:
    """获取Chrome的加密密钥。
    
    Returns:
        Optional[bytes]: 加密密钥
    """
    try:
        # Chrome的Local State文件路径
        local_state_paths = [
            os.path.join(os.environ["LOCALAPPDATA"], "Google/Chrome/User Data/Local State"),
            os.path.join(os.environ["LOCALAPPDATA"], "CentBrowser/User Data/Local State")
        ]
        
        local_state_path = None
        for path in local_state_paths:
            if os.path.exists(path):
                local_state_path = path
                break
                
        if not local_state_path:
            logger.error("未找到Chrome/Cent Browser的Local State文件")
            return None
            
        # 读取Local State文件
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.loads(f.read())
            
        # 获取加密密钥
        encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        encrypted_key = encrypted_key[5:]  # 移除'DPAPI'前缀
        
        # 使用Windows API解密
        decrypted_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
        return decrypted_key
        
    except Exception as e:
        logger.error(f"获取Chrome加密密钥失败: {e}")
        return None

def decrypt_chrome_cookie(encrypted_value: bytes, key: bytes) -> Optional[str]:
    """解密Chrome的Cookie值。
    
    Args:
        encrypted_value: 加密的Cookie值
        key: 加密密钥
        
    Returns:
        Optional[str]: 解密后的Cookie值
    """
    try:
        # 提取初始化向量
        iv = encrypted_value[3:15]
        encrypted_value = encrypted_value[15:]
        
        # 创建cipher对象
        cipher = AES.new(key, AES.MODE_GCM, iv)
        
        # 解密
        decrypted_value = cipher.decrypt(encrypted_value)[:-16].decode()
        return decrypted_value
        
    except Exception as e:
        logger.error(f"解密Cookie值失败: {e}")
        return None

def get_cent_browser_cookies(domain_name: str, browser_path: Optional[str] = None) -> List[Cookie]:
    """获取 Cent Browser 的 Cookie。
    
    Args:
        domain_name: 域名
        browser_path: 浏览器数据目录路径
        
    Returns:
        List[Cookie]: Cookie 列表
    """
    try:
        # 获取Cookie文件路径
        if browser_path:
            cookie_path = Path(browser_path) / "Cookies"
            if not cookie_path.exists():
                cookie_path = Path(browser_path).parent / "Cookies"
        else:
            local_app_data = os.getenv('LOCALAPPDATA')
            if not local_app_data:
                raise ValueError("无法获取 LOCALAPPDATA 环境变量")
                
            cent_paths = [
                Path(local_app_data) / "CentBrowser/User Data/Default/Network/Cookies",
                Path(local_app_data) / "CentBrowser/User Data/Default/Cookies"
            ]
            
            cookie_path = None
            for path in cent_paths:
                if path.exists():
                    cookie_path = path
                    break
                    
        if not cookie_path or not cookie_path.exists():
            raise FileNotFoundError(f"未找到 Cookie 文件: {cookie_path}")
            
        # 获取加密密钥
        key = get_chrome_encryption_key()
        if not key:
            raise ValueError("无法获取加密密钥")
            
        # 连接数据库
        conn = sqlite3.connect(str(cookie_path))
        cursor = conn.cursor()
        
        # 查询Cookie
        cursor.execute(
            "SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly "
            "FROM cookies WHERE host_key LIKE ?",
            (f"%{domain_name}%",)
        )
        
        cookies = []
        for name, encrypted_value, host_key, path, expires_utc, is_secure, is_httponly in cursor.fetchall():
            try:
                # 解密Cookie值
                if encrypted_value[:3] == b'v10':
                    value = decrypt_chrome_cookie(encrypted_value, key)
                else:
                    value = win32crypt.CryptUnprotectData(encrypted_value)[1].decode()
                    
                if value:
                    cookie = Cookie(
                        version=0,
                        name=name,
                        value=value,
                        port=None,
                        port_specified=False,
                        domain=host_key,
                        domain_specified=True,
                        domain_initial_dot=host_key.startswith('.'),
                        path=path,
                        path_specified=True,
                        secure=bool(is_secure),
                        expires=expires_utc,
                        discard=False,
                        comment=None,
                        comment_url=None,
                        rest={},
                        rfc2109=False
                    )
                    cookies.append(cookie)
                    
            except Exception as e:
                logger.error(f"解密Cookie {name} 失败: {e}")
                continue
                
        cursor.close()
        conn.close()
        
        return cookies
        
    except Exception as e:
        logger.error(f"获取 Cent Browser Cookie 失败: {e}")
        return []

class TwitterCookieSyncer:
    """Twitter Cookie 同步器。
    
    从浏览器同步 Twitter Cookie 到配置文件。
    
    Attributes:
        domains: List[str], 要同步的域名列表
        required_cookies: List[str], 必需的 Cookie 名称
        save_path: Path, Cookie 保存路径
        browser_path: Optional[str], 浏览器数据目录路径
    """
    
    # 支持的浏览器列表
    BROWSERS = {
        'chrome': browser_cookie3.chrome,
        'firefox': browser_cookie3.firefox,
        'edge': browser_cookie3.edge,
        'opera': browser_cookie3.opera,
        'brave': browser_cookie3.brave,
        'chromium': browser_cookie3.chromium,
        'vivaldi': browser_cookie3.vivaldi,
        'cent': get_cent_browser_cookies,  # 添加 Cent Browser 支持
    }
    
    def __init__(
        self,
        domains: Optional[List[str]] = None,
        required_cookies: Optional[List[str]] = None,
        save_dir: Optional[Path] = None,
        browser_path: Optional[str] = None
    ):
        """初始化同步器。
        
        Args:
            domains: 要同步的域名列表，默认为 ['twitter.com', 'x.com']
            required_cookies: 必需的 Cookie 名称列表
            save_dir: Cookie 保存目录
            browser_path: 浏览器数据目录路径
        """
        self.domains = domains or ['twitter.com', 'x.com']
        self.required_cookies = required_cookies or [
            'auth_token',  # 认证令牌
            'ct0',         # CSRF 令牌
            'guest_id'     # 访客ID
        ]
        self.save_path = (save_dir or Path('config/cookies')) / 'twitter.json'
        self.browser_path = browser_path
        
    def _get_browser_cookies(
        self,
        browser_func: Callable,
        browser_name: str
    ) -> List[Cookie]:
        """从指定浏览器获取 Cookie。
        
        Args:
            browser_func: browser_cookie3 的浏览器函数
            browser_name: 浏览器名称
            
        Returns:
            List[Cookie]: Cookie 列表
        """
        cookies = []
        for domain in self.domains:
            try:
                # 处理自定义路径
                if self.browser_path:
                    if browser_name == "chrome":
                        cookie_file = os.path.join(self.browser_path, "Cookies")
                        domain_cookies = list(browser_cookie3.chrome(
                            cookie_file=cookie_file,
                            domain_name=domain
                        ))
                    elif browser_name == "firefox":
                        cookie_file = os.path.join(self.browser_path, "cookies.sqlite")
                        domain_cookies = list(browser_cookie3.firefox(
                            cookie_file=cookie_file,
                            domain_name=domain
                        ))
                    elif browser_name == "cent":
                        domain_cookies = get_cent_browser_cookies(
                            domain_name=domain,
                            browser_path=self.browser_path
                        )
                    else:
                        logger.warning(f"不支持自定义路径的浏览器: {browser_name}")
                        continue
                else:
                    if browser_name == "cent":
                        domain_cookies = get_cent_browser_cookies(domain_name=domain)
                    else:
                        domain_cookies = list(browser_func(domain_name=domain))
                
                if domain_cookies:
                    logger.info(
                        f"从 {browser_name} 获取到 {len(domain_cookies)} 个"
                        f" {domain} 的 Cookie"
                    )
                    cookies.extend(domain_cookies)
            except Exception as e:
                logger.error(f"从 {browser_name} 获取 {domain} Cookie 失败: {e}")
                continue
                
        return cookies
        
    def _filter_cookies(self, cookies: List[Cookie]) -> Dict[str, str]:
        """过滤并格式化 Cookie。
        
        Args:
            cookies: Cookie 列表
            
        Returns:
            Dict[str, str]: 有效的 Cookie 字典
        """
        # 按过期时间排序，保留最新的
        sorted_cookies = sorted(
            cookies,
            key=lambda c: c.expires if c.expires else 0,
            reverse=True
        )
        
        # 提取有效的 Cookie
        valid_cookies = {}
        for cookie in sorted_cookies:
            if cookie.name in self.required_cookies and cookie.name not in valid_cookies:
                valid_cookies[cookie.name] = cookie.value
                
        return valid_cookies
        
    def sync(self, browsers: Optional[List[str]] = None) -> bool:
        """同步 Cookie。
        
        Args:
            browsers: 要同步的浏览器列表，默认为所有支持的浏览器
            
        Returns:
            bool: 是否成功同步
        """
        # 确保保存目录存在
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 获取所有 Cookie
        all_cookies = []
        browsers = browsers or list(self.BROWSERS.keys())
        
        for browser_name in browsers:
            browser_func = self.BROWSERS.get(browser_name)
            if browser_func:
                cookies = self._get_browser_cookies(browser_func, browser_name)
                all_cookies.extend(cookies)
                
        # 过滤有效的 Cookie
        valid_cookies = self._filter_cookies(all_cookies)
        
        # 检查是否获取到所有必需的 Cookie
        missing_cookies = set(self.required_cookies) - set(valid_cookies.keys())
        if missing_cookies:
            logger.warning(f"缺少必需的 Cookie: {missing_cookies}")
            
        # 保存 Cookie
        try:
            with open(self.save_path, 'w', encoding='utf-8') as f:
                json.dump(valid_cookies, f, indent=2, ensure_ascii=False)
            logger.info(f"Cookie 已保存到: {self.save_path}")
            return True
        except Exception as e:
            logger.error(f"保存 Cookie 失败: {e}")
            return False
            
def sync_twitter_cookies(
    browsers: Optional[List[str]] = None,
    save_dir: Optional[Path] = None,
    browser_path: Optional[str] = None
) -> bool:
    """同步 Twitter Cookie 的快捷函数。
    
    Args:
        browsers: 要同步的浏览器列表
        save_dir: Cookie 保存目录
        browser_path: 浏览器数据目录路径
        
    Returns:
        bool: 是否成功同步
    """
    syncer = TwitterCookieSyncer(
        save_dir=save_dir,
        browser_path=browser_path
    )
    return syncer.sync(browsers)

def _get_browser_cookies(
    domain: str,
    browsers: List[str],
    browser_path: Optional[str] = None
) -> Dict[str, str]:
    """从浏览器获取指定域名的 Cookie。
    
    Args:
        domain: 域名
        browsers: 浏览器列表
        browser_path: 浏览器数据目录路径
        
    Returns:
        Dict[str, str]: Cookie 字典
    """
    cookies = {}
    
    for browser in browsers:
        try:
            # 获取浏览器实例
            if browser_path:
                # 使用自定义路径
                if browser == "chrome":
                    cj = browser_cookie3.chrome(
                        cookie_file=browser_path + "\\Cookies",
                        domain_name=domain
                    )
                elif browser == "firefox":
                    cj = browser_cookie3.firefox(
                        cookie_file=browser_path + "\\cookies.sqlite",
                        domain_name=domain
                    )
                else:
                    logger.warning(f"不支持自定义路径的浏览器: {browser}")
                    continue
            else:
                # 使用默认路径
                cj = getattr(browser_cookie3, browser)(domain_name=domain)
            
            # 提取Cookie
            for cookie in cj:
                if not cookie.is_expired():
                    cookies[cookie.name] = cookie.value
                    
            if cookies:
                logger.info(f"从 {browser} 获取到 {domain} 的Cookie")
                break
                
        except Exception as e:
            logger.error(f"从 {browser} 获取Cookie失败: {e}")
            continue
            
    return cookies

def sync_youtube_cookies(
    browsers: List[str] = ["chrome"],
    browser_path: Optional[str] = None
) -> bool:
    """同步 YouTube Cookie。
    
    Args:
        browsers: 浏览器列表，默认为 ["chrome"]
        browser_path: 浏览器数据目录路径
        
    Returns:
        bool: 是否成功
    """
    try:
        # 获取YouTube Cookie
        cookies = _get_browser_cookies(
            "youtube.com",
            browsers,
            browser_path
        )
        
        if not cookies:
            logger.warning("未找到YouTube Cookie")
            return False
            
        # 检查登录状态Cookie
        login_cookies = {
            "APISID", "HSID", "SAPISID", "SID", "SSID",  # Google登录Cookie
            "LOGIN_INFO", "PREF"  # YouTube特定Cookie
        }
        if not any(key in cookies for key in login_cookies):
            logger.warning("未检测到YouTube登录状态")
            return False
            
        # 保存Cookie
        cookie_dir = Path("config/cookies")
        cookie_dir.mkdir(parents=True, exist_ok=True)
        
        with open(cookie_dir / "youtube_cookies.json", "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
            
        logger.info("YouTube Cookie已保存")
        return True
        
    except Exception as e:
        logger.error(f"同步YouTube Cookie失败: {e}")
        return False
    
if __name__ == "__main__":
    # 尝试从 Cent Browser 同步
    success = sync_twitter_cookies(browsers=['cent'])
    if success:
        print("Twitter Cookie 同步完成！")
    else:
        print("Twitter Cookie 同步失败！") 