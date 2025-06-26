"""Twitter/X 反爬虫模块。

该模块提供绕过反爬虫机制的功能，包括：
1. Cloudflare 检测绕过
2. Cookies 管理
3. 自动重试机制
"""

import json
import time
import logging
import random
import requests
from pathlib import Path
from typing import Dict, Optional, List
from functools import wraps
from datetime import datetime, timedelta
from urllib.parse import urlparse
from fake_useragent import UserAgent
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from src.core.exceptions import DownloadError

logger = logging.getLogger(__name__)

def retry(max_attempts: int = 3, delay: float = 1.0):
    """重试装饰器。
    
    Args:
        max_attempts: 最大重试次数
        delay: 重试间隔（秒）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"第 {attempt + 1} 次尝试失败: {e}, "
                            f"{delay} 秒后重试..."
                        )
                        time.sleep(delay * (2 ** attempt))  # 指数退避
                    else:
                        logger.error(f"所有重试都失败了: {e}")
                        raise last_error
        return wrapper
    return decorator

class CloudflareBypass:
    """Cloudflare 绕过工具。
    
    使用 selenium-wire 获取有效的 cookies。
    支持自动保存和加载 cookies。
    
    Attributes:
        proxy: Optional[str], 代理服务器地址
        timeout: float, 等待超时时间（秒）
        cookies_file: Path, cookies 保存路径
        user_agent: str, 自定义 User-Agent
        cookies_ttl: int, cookies 有效期（小时）
    """
    
    # Cloudflare 检测特征
    CF_PATTERNS = [
        "challenge-platform",
        "cf-browser-verification",
        "_cf_chl_opt",
        "cf_clearance"
    ]
    
    def __init__(self, 
                 proxy: Optional[str] = None,
                 timeout: float = 30.0,
                 cookies_file: Optional[Path] = None,
                 user_agent: Optional[str] = None,
                 cookies_ttl: int = 24):
        """初始化 Cloudflare 绕过工具。
        
        Args:
            proxy: 代理服务器地址
            timeout: 等待超时时间
            cookies_file: cookies 保存路径，默认为 .twitter_cookies
            user_agent: 自定义 User-Agent，如果不指定则随机生成
            cookies_ttl: cookies 有效期（小时）
        """
        self.proxy = proxy
        self.timeout = timeout
        self.cookies_file = cookies_file or Path.home() / ".twitter_cookies"
        self.user_agent = user_agent or UserAgent().random
        self.cookies_ttl = cookies_ttl
        
    def _setup_driver(self) -> webdriver.Chrome:
        """配置 Chrome WebDriver。
        
        Returns:
            webdriver.Chrome: 配置好的 WebDriver 实例
        """
        options = Options()
        
        # 基本配置
        options.add_argument("--headless")  # 无头模式
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        
        # 高级配置
        options.add_argument(f"user-agent={self.user_agent}")
        options.add_argument("--disable-blink-features=AutomationControlled")  # 隐藏自动化特征
        options.add_argument("--disable-infobars")  # 禁用信息栏
        options.add_argument("--disable-notifications")  # 禁用通知
        options.add_argument("--ignore-certificate-errors")  # 忽略证书错误
        options.add_argument("--disable-web-security")  # 禁用 Web 安全策略
        
        # 性能优化
        options.add_argument("--disable-logging")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-javascript")  # 禁用 JavaScript（可选）
        options.add_argument("--disable-images")  # 禁用图片加载（可选）
        
        # 随机窗口大小（避免指纹识别）
        window_sizes = [(1366, 768), (1920, 1080), (1440, 900), (1600, 900)]
        width, height = random.choice(window_sizes)
        options.add_argument(f"--window-size={width},{height}")
        
        # 配置代理
        seleniumwire_options = {
            "verify_ssl": False,  # 禁用 SSL 验证
            "suppress_connection_errors": True  # 抑制连接错误
        }
        
        if self.proxy:
            seleniumwire_options["proxy"] = {
                "http": self.proxy,
                "https": self.proxy
            }
            
        # 创建 WebDriver
        driver = webdriver.Chrome(
            options=options,
            seleniumwire_options=seleniumwire_options
        )
        
        # 配置请求拦截（可以修改请求头）
        def interceptor(request):
            # 添加自定义请求头
            request.headers["User-Agent"] = self.user_agent
            request.headers["Accept-Language"] = "en-US,en;q=0.9"
            request.headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            
        driver.request_interceptor = interceptor
        driver.set_page_load_timeout(self.timeout)
        
        return driver
        
    def _wait_for_cloudflare(self, driver: webdriver.Chrome) -> None:
        """等待 Cloudflare 检查完成。
        
        Args:
            driver: WebDriver 实例
            
        Raises:
            TimeoutException: 等待超时
        """
        try:
            # 等待页面加载完成
            WebDriverWait(driver, self.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 检查是否存在 Cloudflare 挑战
            for pattern in self.CF_PATTERNS:
                if pattern in driver.page_source:
                    logger.info(f"检测到 Cloudflare 特征: {pattern}")
                    # 等待挑战完成
                    self._solve_challenge(driver)
                    break
                    
        except TimeoutException as e:
            logger.error("等待 Cloudflare 检查超时")
            raise DownloadError("Cloudflare 检查超时") from e
            
    def _solve_challenge(self, driver: webdriver.Chrome) -> None:
        """尝试解决 Cloudflare 挑战。
        
        Args:
            driver: WebDriver 实例
        """
        # 等待挑战元素出现
        try:
            # 等待 "Checking your browser" 消失
            WebDriverWait(driver, 10).until_not(
                EC.presence_of_element_located((By.ID, "cf-spinner-please-wait"))
            )
            
            # 检查是否需要点击验证按钮
            verify_button = driver.find_elements(By.ID, "challenge-stage")
            if verify_button:
                verify_button[0].click()
                logger.info("点击了验证按钮")
                
            # 给予足够时间完成验证
            time.sleep(random.uniform(5, 8))
            
        except Exception as e:
            logger.warning(f"解决挑战时出错: {e}")
            
    def _save_cookies(self, cookies: Dict) -> None:
        """保存 cookies 到文件。
        
        Args:
            cookies: cookies 字典
        """
        try:
            data = {
                "cookies": cookies,
                "timestamp": datetime.now().isoformat(),
                "user_agent": self.user_agent
            }
            with open(self.cookies_file, "w") as f:
                json.dump(data, f)
            logger.info(f"Cookies 已保存到: {self.cookies_file}")
        except Exception as e:
            logger.error(f"保存 cookies 失败: {e}")
            
    def _load_cookies(self) -> Optional[Dict]:
        """从文件加载 cookies。
        
        Returns:
            Optional[Dict]: cookies 字典，如果文件不存在或已过期则返回 None
        """
        try:
            if self.cookies_file.exists():
                with open(self.cookies_file) as f:
                    data = json.load(f)
                    
                # 检查 cookies 是否过期
                saved_time = datetime.fromisoformat(data["timestamp"])
                if datetime.now() - saved_time > timedelta(hours=self.cookies_ttl):
                    logger.info("Cookies 已过期")
                    return None
                    
                # 验证 cookies 有效性
                if self._verify_cookies(data["cookies"]):
                    logger.info(f"已从 {self.cookies_file} 加载有效的 cookies")
                    return data["cookies"]
                else:
                    logger.warning("已保存的 cookies 无效")
                    return None
                    
        except Exception as e:
            logger.error(f"加载 cookies 失败: {e}")
        return None
        
    def _verify_cookies(self, cookies: Dict) -> bool:
        """验证 cookies 是否有效。
        
        Args:
            cookies: cookies 字典
            
        Returns:
            bool: cookies 是否有效
        """
        try:
            # 构建请求头
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())
            }
            
            # 发送测试请求
            response = requests.get(
                "https://twitter.com/i/api/2/guide.json",
                headers=headers,
                proxies={"http": self.proxy, "https": self.proxy} if self.proxy else None,
                timeout=self.timeout,
                verify=False
            )
            
            # 检查响应
            return response.status_code == 200 and "cf_clearance" not in response.text
            
        except Exception as e:
            logger.warning(f"验证 cookies 时出错: {e}")
            return False
            
    @retry(max_attempts=3, delay=2.0)
    def bypass_cloudflare(self, url: str) -> Dict:
        """绕过 Cloudflare 检测并获取 cookies。
        
        Args:
            url: 目标URL
            
        Returns:
            Dict: 包含有效 cookies 的字典
            
        Raises:
            DownloadError: 绕过失败
        """
        # 尝试加载已保存的 cookies
        cookies = self._load_cookies()
        if cookies:
            return cookies
            
        try:
            # 创建 WebDriver
            driver = self._setup_driver()
            
            try:
                # 访问目标页面
                logger.info(f"正在访问: {url}")
                driver.get(url)
                
                # 等待 Cloudflare 检查完成
                self._wait_for_cloudflare(driver)
                
                # 获取 cookies
                cookies = {}
                for cookie in driver.get_cookies():
                    cookies[cookie["name"]] = cookie["value"]
                    
                # 验证新获取的 cookies
                if not self._verify_cookies(cookies):
                    raise DownloadError("获取的 cookies 无效")
                    
                # 保存 cookies
                self._save_cookies(cookies)
                
                return cookies
                
            finally:
                # 确保关闭浏览器
                driver.quit()
                
        except Exception as e:
            logger.error(f"绕过 Cloudflare 失败: {e}")
            raise DownloadError(f"绕过 Cloudflare 失败: {e}")
            
def bypass_cloudflare(url: str, 
                     proxy: Optional[str] = None,
                     timeout: float = 30.0) -> Dict:
    """便捷函数：绕过 Cloudflare 检测。
    
    Args:
        url: 目标URL
        proxy: 可选的代理服务器地址
        timeout: 超时时间（秒）
        
    Returns:
        Dict: 包含有效 cookies 的字典
        
    Raises:
        DownloadError: 绕过失败
    """
    bypass = CloudflareBypass(proxy=proxy, timeout=timeout)
    return bypass.bypass_cloudflare(url) 