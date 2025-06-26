"""Twitter信息提取器测试模块。

测试推文和媒体信息提取功能。
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webelement import WebElement
from src.plugins.twitter.extractor import TwitterExtractor
from src.core.exceptions import ExtractError

@pytest.fixture
def extractor():
    """创建TwitterExtractor实例。"""
    return TwitterExtractor()

@pytest.fixture
def mock_graphql(mocker):
    """模拟GraphQL客户端。"""
    client = Mock()
    mocker.patch('src.plugins.twitter.extractor.GraphQLClient', return_value=client)
    return client

@pytest.fixture
def tweet_data():
    """加载测试用推文数据。"""
    return {
        'data': {
            'tweet': {
                'id': '1234567890',
                'text': 'Test tweet with media',
                'author': {
                    'id': '987654321',
                    'name': 'Test User',
                    'screen_name': 'testuser'
                },
                'created_at': '2024-01-01T12:00:00Z',
                'media': [
                    {
                        'type': 'photo',
                        'url': 'https://example.com/photo.jpg',
                        'width': 1280,
                        'height': 720
                    },
                    {
                        'type': 'video',
                        'variants': [
                            {
                                'bitrate': 832000,
                                'content_type': 'video/mp4',
                                'url': 'https://example.com/video_720p.mp4'
                            },
                            {
                                'bitrate': 2176000,
                                'content_type': 'video/mp4',
                                'url': 'https://example.com/video_1080p.mp4'
                            }
                        ]
                    }
                ]
            }
        }
    }

@pytest.fixture
def mock_driver():
    """创建模拟的 WebDriver。"""
    driver = MagicMock()
    driver.find_elements.return_value = []
    return driver

@pytest.fixture
def extractor(mock_driver):
    """创建测试用的提取器实例。"""
    return TwitterExtractor(driver=mock_driver)

def test_init(extractor):
    """测试初始化。"""
    assert extractor.client is not None
    assert extractor.headers is not None
    assert 'User-Agent' in extractor.headers

def test_extract_tweet_info_success(extractor, mock_graphql, tweet_data):
    """测试成功提取推文信息。"""
    mock_graphql.execute.return_value = tweet_data

    info = extractor.extract_tweet_info('1234567890')
    assert info['id'] == '1234567890'
    assert info['text'] == 'Test tweet with media'
    assert info['author']['name'] == 'Test User'
    assert len(info['media']) == 2

def test_extract_tweet_info_429(extractor, mock_graphql):
    """测试429错误处理。"""
    mock_graphql.execute.side_effect = Exception('Rate limited')

    with pytest.raises(ExtractError, match='Rate limited'):
        extractor.extract_tweet_info('1234567890')

def test_extract_tweet_info_retry(extractor, mock_graphql, tweet_data):
    """测试重试机制。"""
    mock_graphql.execute.side_effect = [
        Exception('Rate limited'),
        tweet_data
    ]

    info = extractor.extract_tweet_info('1234567890', max_retries=2)
    assert info['id'] == '1234567890'
    assert mock_graphql.execute.call_count == 2

def test_extract_media_urls(extractor, tweet_data):
    """测试提取媒体URL。"""
    urls = extractor._extract_media_urls(tweet_data['data']['tweet']['media'])
    assert len(urls) == 2
    assert urls[0] == 'https://example.com/photo.jpg'
    assert urls[1] == 'https://example.com/video_1080p.mp4'

def test_extract_media_urls_empty(extractor):
    """测试提取空媒体列表。"""
    urls = extractor._extract_media_urls([])
    assert len(urls) == 0

def test_get_best_video_variant(extractor):
    """测试选择最佳视频质量。"""
    variants = [
        {'bitrate': 832000, 'url': 'low.mp4'},
        {'bitrate': 2176000, 'url': 'high.mp4'},
        {'bitrate': 1024000, 'url': 'medium.mp4'}
    ]
    best = extractor._get_best_video_variant(variants)
    assert best['url'] == 'high.mp4'

def test_get_best_video_variant_empty(extractor):
    """测试空视频变体列表。"""
    assert extractor._get_best_video_variant([]) is None

def test_extract_tweet_info_invalid_id(extractor):
    """测试无效的推文ID。"""
    with pytest.raises(ValueError, match='Invalid tweet ID'):
        extractor.extract_tweet_info('')

def test_extract_tweet_info_not_found(extractor, mock_graphql):
    """测试推文不存在。"""
    mock_graphql.execute.return_value = {'data': {'tweet': None}}

    with pytest.raises(ExtractError, match='Tweet not found'):
        extractor.extract_tweet_info('1234567890')

@pytest.mark.asyncio
async def test_async_extract_tweet_info(extractor, mock_graphql, tweet_data):
    """测试异步提取推文信息。"""
    mock_graphql.execute.return_value = tweet_data

    info = await extractor.async_extract_tweet_info('1234567890')
    assert info['id'] == '1234567890'
    assert info['text'] == 'Test tweet with media'

def test_extract_tweet_info_with_proxy(extractor, mock_graphql, tweet_data):
    """测试使用代理提取信息。"""
    mock_graphql.execute.return_value = tweet_data
    proxy = 'http://127.0.0.1:7890'

    info = extractor.extract_tweet_info('1234567890', proxy=proxy)
    assert info['id'] == '1234567890'
    assert mock_graphql.proxy == proxy

def test_parse_tweet_url(extractor):
    """测试解析推文URL。"""
    urls = [
        'https://twitter.com/user/status/1234567890',
        'https://x.com/user/status/1234567890',
        'https://mobile.twitter.com/user/status/1234567890'
    ]
    for url in urls:
        tweet_id = extractor.parse_tweet_url(url)
        assert tweet_id == '1234567890'

def test_parse_tweet_url_invalid(extractor):
    """测试解析无效的URL。"""
    invalid_urls = [
        'https://twitter.com/user',
        'https://example.com/1234567890',
        'invalid_url'
    ]
    for url in invalid_urls:
        with pytest.raises(ValueError, match='Invalid tweet URL'):
            extractor.parse_tweet_url(url)

def test_extract_tweet_info_with_cookies(extractor, mock_graphql, tweet_data):
    """测试使用cookies提取信息。"""
    mock_graphql.execute.return_value = tweet_data
    cookies = {'auth_token': 'test_token'}

    info = extractor.extract_tweet_info('1234567890', cookies=cookies)
    assert info['id'] == '1234567890'
    assert 'auth_token' in extractor.client.headers.get('Cookie', '')

def test_valid_tweet_urls(extractor):
    """测试推文 URL 验证。"""
    # 有效的 URL
    valid_urls = [
        "https://twitter.com/username/status/123456789",
        "https://x.com/username/status/123456789",
    ]
    for url in valid_urls:
        assert extractor._is_valid_tweet_url(url)
        
    # 无效的 URL
    invalid_urls = [
        "https://twitter.com/username",
        "https://twitter.com/status/123456789",
        "https://other.com/username/status/123456789",
        "invalid_url",
        "",
        None
    ]
    for url in invalid_urls:
        assert not extractor._is_valid_tweet_url(url)

def test_extract_image(extractor, mock_driver):
    """测试图片提取。"""
    # 模拟图片元素
    mock_img = MagicMock(spec=WebElement)
    mock_img.get_attribute.return_value = "https://example.com/image.jpg"
    
    mock_element = MagicMock(spec=WebElement)
    mock_element.get_attribute.return_value = "tweetPhoto"
    mock_element.find_element.return_value = mock_img
    mock_element.find_elements.return_value = []  # 没有 playButton，所以不是 GIF
    
    # 设置返回值
    mock_driver.find_elements.return_value = [mock_element]
    
    # 提取信息
    info = extractor.extract_info("https://twitter.com/username/status/123456789")
    
    assert info == {
        "media": [{
            "url": "https://example.com/image.jpg",
            "type": "image"
        }]
    }

def test_extract_gif(extractor, mock_driver):
    """测试 GIF 提取。"""
    # 模拟 GIF 元素
    mock_img = MagicMock(spec=WebElement)
    mock_img.get_attribute.return_value = "https://example.com/image.gif"
    
    mock_element = MagicMock(spec=WebElement)
    mock_element.get_attribute.return_value = "tweetPhoto"
    mock_element.find_element.return_value = mock_img
    # 存在 playButton，说明是 GIF
    mock_element.find_elements.return_value = [MagicMock()]
    
    # 设置返回值
    mock_driver.find_elements.return_value = [mock_element]
    
    # 提取信息
    info = extractor.extract_info("https://twitter.com/username/status/123456789")
    
    assert info == {
        "media": [{
            "url": "https://example.com/image.gif",
            "type": "gif"
        }]
    }

def test_extract_video(extractor, mock_driver):
    """测试视频提取。"""
    # 模拟视频元素
    mock_video = MagicMock(spec=WebElement)
    mock_video.get_attribute.return_value = "https://example.com/video.mp4"
    
    mock_element = MagicMock(spec=WebElement)
    mock_element.get_attribute.return_value = "videoPlayer"
    mock_element.find_element.return_value = mock_video
    
    # 设置返回值
    mock_driver.find_elements.return_value = [mock_element]
    mock_driver.execute_script.return_value = 120.5  # 视频时长
    
    # 提取信息
    info = extractor.extract_info("https://twitter.com/username/status/123456789")
    
    assert info == {
        "media": [{
            "url": "https://example.com/video.mp4",
            "type": "video",
            "duration": 120.5
        }]
    }

def test_extract_multiple_media(extractor, mock_driver):
    """测试多媒体提取。"""
    # 模拟图片元素
    mock_img = MagicMock(spec=WebElement)
    mock_img.get_attribute.return_value = "https://example.com/image.jpg"
    mock_img_element = MagicMock(spec=WebElement)
    mock_img_element.get_attribute.return_value = "tweetPhoto"
    mock_img_element.find_element.return_value = mock_img
    mock_img_element.find_elements.return_value = []
    
    # 模拟视频元素
    mock_video = MagicMock(spec=WebElement)
    mock_video.get_attribute.return_value = "https://example.com/video.mp4"
    mock_video_element = MagicMock(spec=WebElement)
    mock_video_element.get_attribute.return_value = "videoPlayer"
    mock_video_element.find_element.return_value = mock_video
    
    # 设置返回值
    mock_driver.find_elements.return_value = [mock_img_element, mock_video_element]
    mock_driver.execute_script.return_value = 60.0
    
    # 提取信息
    info = extractor.extract_info("https://twitter.com/username/status/123456789")
    
    assert info == {
        "media": [
            {
                "url": "https://example.com/image.jpg",
                "type": "image"
            },
            {
                "url": "https://example.com/video.mp4",
                "type": "video",
                "duration": 60.0
            }
        ]
    }

def test_no_media(extractor, mock_driver):
    """测试无媒体内容。"""
    # 设置返回空列表
    mock_driver.find_elements.return_value = []
    
    # 提取信息
    info = extractor.extract_info("https://twitter.com/username/status/123456789")
    
    assert info == {"media": []}

def test_invalid_url(extractor):
    """测试无效 URL。"""
    with pytest.raises(ValueError, match="无效的推文 URL"):
        extractor.extract_info("https://invalid.com")

def test_media_load_timeout(extractor, mock_driver):
    """测试媒体加载超时。"""
    # 模拟等待超时
    mock_driver.get.side_effect = TimeoutException("加载超时")
    
    with pytest.raises(TimeoutException):
        extractor.extract_info("https://twitter.com/username/status/123456789")

def test_resource_cleanup(mock_driver):
    """测试资源清理。"""
    extractor = TwitterExtractor(driver=mock_driver)
    
    # 测试上下文管理器
    with extractor:
        pass
    
    # 验证 driver 被正确关闭
    mock_driver.quit.assert_called_once()
    assert extractor.driver is None

def test_extract_info_error_handling(extractor, mock_driver):
    """测试信息提取错误处理。"""
    # 模拟元素查找失败
    mock_driver.find_elements.side_effect = Exception("元素查找失败")
    
    with pytest.raises(Exception, match="元素查找失败"):
        extractor.extract_info("https://twitter.com/username/status/123456789")

@patch('selenium.webdriver.Chrome')
def test_driver_creation(mock_chrome):
    """测试 WebDriver 创建。"""
    TwitterExtractor()
    
    # 验证 Chrome 实例被创建，并设置了正确的选项
    mock_chrome.assert_called_once()
    options = mock_chrome.call_args[1]['options']
    assert "--headless" in options.arguments
    assert "--disable-gpu" in options.arguments
    assert "--no-sandbox" in options.arguments
    assert "--disable-dev-shm-usage" in options.arguments 