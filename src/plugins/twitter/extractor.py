"""Twitter 媒体提取模块。

负责从 Twitter 页面提取媒体信息，包括图片、视频和 GIF。
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from playwright.sync_api import Page

logger = logging.getLogger(__name__)

class TwitterExtractor:
    """Twitter 媒体提取器。
    
    负责从 Twitter 页面提取媒体信息，包括：
    - 图片
    - 视频
    - GIF
    
    支持提取视频时长信息。
    
    Attributes:
        driver: webdriver.Chrome, Chrome WebDriver 实例
        wait_timeout: int, 等待超时时间（秒）
    """
    
    # 视频元素选择器列表
    VIDEO_SELECTORS = [
        "video",  # 标准video标签
        "div[data-testid='videoPlayer'] video",  # Twitter视频播放器
        "div[data-testid='videoComponent'] video",  # Twitter视频组件
        "div[data-testid='media'] video",  # 媒体容器中的视频
        "article video",  # 文章中的视频
    ]
    
    # 图片元素选择器列表
    IMAGE_SELECTORS = [
        "img[src*='media']",  # 媒体图片
        "div[data-testid='media'] img",  # 媒体容器中的图片
        "article img[src*='media']",  # 文章中的媒体图片
    ]
    
    def __init__(
        self,
        driver: Optional[webdriver.Chrome] = None,
        wait_timeout: int = 30
    ):
        """初始化提取器。
        
        Args:
            driver: Chrome WebDriver 实例，如果不提供则创建新实例
            wait_timeout: 等待超时时间（秒）
        """
        self.driver = driver or self._create_driver()
        self.wait_timeout = wait_timeout
        
    def _create_driver(self) -> webdriver.Chrome:
        """创建 Chrome WebDriver 实例。
        
        Returns:
            webdriver.Chrome: WebDriver 实例
        """
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # 无界面模式
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        return webdriver.Chrome(options=options)
        
    def extract_info(self, url: str) -> Dict[str, Any]:
        """提取推文中的媒体信息。
        
        Args:
            url: 推文URL
            
        Returns:
            Dict[str, Any]: 媒体信息，格式如下：
            {
                "media": [
                    {
                        "url": "https://...",
                        "type": "video",  # video/image/gif
                        "duration": 120    # 仅视频有效，单位秒
                    }
                ]
            }
            
        Raises:
            ValueError: URL 无效
            requests.RequestException: 网络请求失败
        """
        try:
            # 验证 URL
            if not self._is_valid_tweet_url(url):
                raise ValueError(f"无效的推文 URL: {url}")
                
            # 加载页面
            self.driver.get(url)
            
            # 等待媒体元素加载
            self._wait_for_media()
            
            # 提取媒体信息
            media_elements = self._find_media_elements()
            media_info = []
            
            for element in media_elements:
                info = self._extract_media_info(element)
                if info:
                    media_info.append(info)
                    
            return {"media": media_info}
            
        except Exception as e:
            logger.error(f"提取媒体信息失败: {e}")
            raise
            
    def _is_valid_tweet_url(self, url: str) -> bool:
        """验证推文 URL 是否有效。
        
        Args:
            url: 推文 URL
            
        Returns:
            bool: URL 是否有效
        """
        try:
            parsed = urlparse(url)
            return (
                parsed.netloc in ("twitter.com", "x.com") and
                bool(re.match(r"/\w+/status/\d+", parsed.path))
            )
        except Exception:
            return False
            
    def _wait_for_media(self) -> None:
        """等待媒体元素加载完成。
        
        Raises:
            TimeoutException: 等待超时
        """
        wait = WebDriverWait(self.driver, self.wait_timeout)
        
        # 等待图片加载
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, '[data-testid="tweetPhoto"]')
            ),
            message="等待图片加载超时"
        )
        
        # 等待视频加载
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, '[data-testid="videoPlayer"]')
            ),
            message="等待视频加载超时"
        )
        
    def _find_media_elements(self) -> List[Any]:
        """查找所有媒体元素。
        
        Returns:
            List[Any]: 媒体元素列表
        """
        return self.driver.find_elements(
            By.CSS_SELECTOR,
            '[data-testid="tweetPhoto"], [data-testid="videoPlayer"]'
        )
        
    def _extract_media_info(self, element: Any) -> Optional[Dict[str, Any]]:
        """从媒体元素提取信息。
        
        Args:
            element: 媒体元素
            
        Returns:
            Optional[Dict[str, Any]]: 媒体信息，格式如下：
            {
                "url": "https://...",
                "type": "video",  # video/image/gif
                "duration": 120    # 仅视频有效
            }
        """
        try:
            # 获取元素类型
            test_id = element.get_attribute("data-testid")
            
            if test_id == "tweetPhoto":
                # 提取图片信息
                return self._extract_image_info(element)
            elif test_id == "videoPlayer":
                # 提取视频信息
                return self._extract_video_info(element)
                
        except Exception as e:
            logger.warning(f"提取媒体信息失败: {e}")
            return None
            
    def _extract_image_info(self, element: Any) -> Dict[str, Any]:
        """提取图片信息。
        
        Args:
            element: 图片元素
            
        Returns:
            Dict[str, Any]: 图片信息
        """
        # 获取图片 URL
        img = element.find_element(By.TAG_NAME, "img")
        url = img.get_attribute("src")
        
        # 判断是否为 GIF
        is_gif = bool(element.find_elements(
            By.CSS_SELECTOR,
            '[data-testid="playButton"]'
        ))
        
        return {
            "url": url,
            "type": "gif" if is_gif else "image"
        }
        
    def _extract_video_info(self, element: Any) -> Dict[str, Any]:
        """提取视频信息。
        
        Args:
            element: 视频元素
            
        Returns:
            Dict[str, Any]: 视频信息
        """
        # 获取视频 URL
        video = element.find_element(By.TAG_NAME, "video")
        url = video.get_attribute("src")
        
        # 获取视频时长
        duration = self._get_video_duration(video)
        
        return {
            "url": url,
            "type": "video",
            "duration": duration
        }
        
    def _get_video_duration(self, video_element: Any) -> float:
        """获取视频时长。
        
        Args:
            video_element: 视频元素
            
        Returns:
            float: 视频时长（秒）
        """
        # 执行 JS 获取时长
        duration = self.driver.execute_script(
            "return arguments[0].duration",
            video_element
        )
        return float(duration)
        
    def close(self) -> None:
        """关闭 WebDriver。"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            
    def __enter__(self):
        """上下文管理器入口。"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        self.close()

    def extract_media(self, page: Page) -> List[str]:
        """提取页面中的媒体URL。
        
        Args:
            page: Playwright页面对象
            
        Returns:
            List[str]: 媒体URL列表
        """
        urls = []
        
        # 提取视频URL
        for selector in self.VIDEO_SELECTORS:
            elements = page.query_selector_all(selector)
            for element in elements:
                # 获取video标签的src属性
                src = element.get_attribute("src")
                if src:
                    urls.append(src)
                    logger.info(f"找到视频URL(从src): {src}")
                    
                # 获取source标签的src属性
                sources = element.query_selector_all("source")
                for source in sources:
                    src = source.get_attribute("src")
                    if src:
                        urls.append(src)
                        logger.info(f"找到视频URL(从source): {src}")
                        
        # 如果没有找到视频，尝试提取图片URL
        if not urls:
            for selector in self.IMAGE_SELECTORS:
                elements = page.query_selector_all(selector)
                for element in elements:
                    src = element.get_attribute("src")
                    if src and "media" in src:
                        # 获取最高质量的图片URL
                        best_url = src
                        if "format=jpg&name=large" in src:
                            best_url = src
                            
                        urls.append(best_url)
                        logger.info(f"找到图片URL: {best_url}")
                        
        return urls 