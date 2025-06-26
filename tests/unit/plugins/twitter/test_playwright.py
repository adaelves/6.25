"""Twitter视频提取测试模块。

使用Playwright进行Twitter视频提取的测试。
"""

import os
import time
import pytest
from unittest.mock import Mock
from playwright.sync_api import (
    sync_playwright,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError
)

from src.plugins.twitter.extractor import TwitterExtractor
from src.plugins.twitter.downloader import TwitterDownloader
from src.plugins.twitter.config import TwitterDownloaderConfig

# 测试资源目录
TEST_RESOURCES = os.path.join(os.path.dirname(__file__), "resources")

@pytest.fixture(scope="module")
def mock_page():
    """创建Playwright页面对象。
    
    Returns:
        Page: Playwright页面对象
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        yield page
        browser.close()

@pytest.fixture(scope="module")
def extractor():
    """创建Twitter提取器实例。
    
    Returns:
        TwitterExtractor: Twitter提取器实例
    """
    return TwitterExtractor()

@pytest.fixture(scope="module")
def downloader():
    """创建Twitter下载器实例。
    
    Returns:
        TwitterDownloader: Twitter下载器实例
    """
    config = TwitterDownloaderConfig(
        save_dir="downloads",
        max_retries=3,
        retry_interval=0.1  # 测试时使用较短的重试间隔
    )
    return TwitterDownloader(config=config)

@pytest.fixture(scope="module")
def test_html_path():
    """获取测试HTML文件路径。
    
    Returns:
        str: 测试HTML文件的绝对路径
    """
    return os.path.join(TEST_RESOURCES, "test_twitter_video.html")

def test_video_extraction(mock_page, extractor, test_html_path):
    """测试从Twitter页面提取视频URL。
    
    Args:
        mock_page: Playwright页面对象
        extractor: Twitter提取器实例
        test_html_path: 测试HTML文件路径
    """
    # 加载测试HTML文件
    mock_page.goto(f"file:///{test_html_path}")
    
    # 提取视频URL
    urls = extractor.extract_media(mock_page)
    
    # 验证结果
    assert len(urls) > 0
    assert any("video.twimg.com" in url for url in urls)

def test_video_extraction_with_retry(mock_page, downloader, test_html_path):
    """测试带重试机制的视频提取。
    
    Args:
        mock_page: Playwright页面对象
        downloader: Twitter下载器实例
        test_html_path: 测试HTML文件路径
    """
    # 加载测试HTML文件
    mock_page.goto(f"file:///{test_html_path}")
    
    # 提取视频URL
    urls = downloader.download_video(mock_page)
    
    # 验证结果
    assert len(urls) > 0
    assert any("video.twimg.com" in url for url in urls)

def test_video_extraction_timeout(mock_page, downloader):
    """测试视频提取超时处理。
    
    Args:
        mock_page: Playwright页面对象
        downloader: Twitter下载器实例
    """
    # 创建一个空白页面（不包含视频元素）
    mock_page.set_content("<html><body></body></html>")
    
    # 验证超时异常
    with pytest.raises(PlaywrightTimeoutError):
        downloader.download_video(mock_page)

def test_video_extraction_detached(mock_page, downloader, test_html_path):
    """测试视频元素分离的情况。
    
    Args:
        mock_page: Playwright页面对象
        downloader: Twitter下载器实例
        test_html_path: 测试HTML文件路径
    """
    # 加载测试HTML文件
    mock_page.goto(f"file:///{test_html_path}")
    
    # 模拟元素分离
    mock_page.evaluate("""() => {
        const video = document.querySelector('video');
        if (video) video.remove();
    }""")
    
    # 验证超时异常
    with pytest.raises(PlaywrightError) as exc_info:
        downloader.download_video(mock_page)
    assert "Timeout" in str(exc_info.value)

def test_video_extraction_retry_success(mock_page, downloader, test_html_path):
    """测试重试后成功的情况。
    
    Args:
        mock_page: Playwright页面对象
        downloader: Twitter下载器实例
        test_html_path: 测试HTML文件路径
    """
    # 计数器用于模拟前两次失败
    attempt_count = 0
    
    def mock_wait_for_video(page):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count <= 2:  # 前两次调用时抛出异常
            raise PlaywrightTimeoutError("模拟超时")
    
    # 替换原始的等待方法
    original_wait = downloader._wait_for_video
    downloader._wait_for_video = mock_wait_for_video
    
    try:
        # 加载测试HTML文件
        mock_page.goto(f"file:///{test_html_path}")
        
        # 提取视频URL（应该在第三次尝试时成功）
        urls = downloader.download_video(mock_page)
        
        # 验证结果
        assert len(urls) > 0
        assert any("video.twimg.com" in url for url in urls)
        assert attempt_count == 3  # 确认重试了两次
        
    finally:
        # 恢复原始方法
        downloader._wait_for_video = original_wait

def test_video_extraction_max_retries_exceeded(mock_page, downloader):
    """测试超过最大重试次数的情况。
    
    Args:
        mock_page: Playwright页面对象
        downloader: Twitter下载器实例
    """
    # 模拟始终失败的等待方法
    def mock_wait_for_video(page):
        raise PlaywrightTimeoutError("模拟超时")
    
    # 替换原始的等待方法
    original_wait = downloader._wait_for_video
    downloader._wait_for_video = mock_wait_for_video
    
    try:
        # 创建一个空白页面
        mock_page.set_content("<html><body></body></html>")
        
        # 验证达到最大重试次数后抛出异常
        with pytest.raises(PlaywrightTimeoutError) as exc_info:
            downloader.download_video(mock_page)
            
        # 验证错误消息
        assert "模拟超时" in str(exc_info.value)
        
    finally:
        # 恢复原始方法
        downloader._wait_for_video = original_wait 