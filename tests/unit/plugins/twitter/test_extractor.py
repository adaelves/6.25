"""Twitter信息提取器测试模块。

测试推文和媒体信息提取功能。
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
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