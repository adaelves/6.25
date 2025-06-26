"""Twitter下载器测试模块。

测试推文媒体下载功能。
"""

import os
import json
import pytest
import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import requests

from src.plugins.twitter.config import TwitterDownloaderConfig
from src.plugins.twitter.downloader import TwitterDownloader, SpeedLimiter
from src.core.config import DownloaderConfig
from src.core.exceptions import DownloadError

@pytest.fixture
def config():
    """创建下载器配置。"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield DownloaderConfig(
            save_dir=Path(temp_dir),
            max_concurrent_downloads=2,
            speed_limit=1024 * 1024,  # 1MB/s
            chunk_size=8192
        )

@pytest.fixture
def mock_extractor(mocker):
    """模拟信息提取器。"""
    extractor = Mock()
    mocker.patch('src.plugins.twitter.downloader.TwitterExtractor', return_value=extractor)
    return extractor

@pytest.fixture
def downloader(config):
    """创建TwitterDownloader实例。"""
    return TwitterDownloader(config)

@pytest.fixture
def tweet_info():
    """测试用推文信息。"""
    return {
        'id': '1234567890',
        'text': 'Test tweet with media',
        'author': {
            'name': 'Test User',
            'screen_name': 'testuser'
        },
        'created_at': '2024-01-01T12:00:00Z',
        'media': [
            {
                'type': 'photo',
                'url': 'https://example.com/photo.jpg'
            },
            {
                'type': 'video',
                'url': 'https://example.com/video.mp4'
            }
        ]
    }

def test_init(downloader):
    """测试初始化。"""
    assert downloader.config is not None
    assert downloader.extractor is not None
    assert downloader.speed_limiter is not None

def test_download_media_success(downloader, mock_extractor, tweet_info):
    """测试成功下载媒体。"""
    # 模拟提取器返回
    mock_extractor.extract_tweet_info.return_value = tweet_info
    
    # 模拟下载响应
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-length': '1024'}
    mock_response.iter_content.return_value = [b'test data']
    
    with patch('requests.get', return_value=mock_response):
        result = downloader.download('https://twitter.com/user/status/1234567890')
        assert result
        
        # 验证文件是否下载
        for media in tweet_info['media']:
            filename = f"{tweet_info['author']['screen_name']}_{tweet_info['id']}_{media['type']}"
            file_path = downloader.config.save_dir / filename
            assert file_path.exists()

def test_download_media_429(downloader, mock_extractor, tweet_info):
    """测试429错误处理。"""
    mock_extractor.extract_tweet_info.return_value = tweet_info
    
    # 模拟429响应
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError('Rate limited')
    
    with patch('requests.get', return_value=mock_response):
        with pytest.raises(DownloadError, match='Rate limited'):
            downloader.download('https://twitter.com/user/status/1234567890')

def test_download_media_retry(downloader, mock_extractor, tweet_info):
    """测试重试机制。"""
    mock_extractor.extract_tweet_info.return_value = tweet_info
    
    # 模拟响应序列：429 -> 200
    responses = [
        Mock(status_code=429, raise_for_status=Mock(side_effect=requests.exceptions.HTTPError('Rate limited'))),
        Mock(status_code=200, headers={'content-length': '1024'}, iter_content=Mock(return_value=[b'test data']))
    ]
    
    with patch('requests.get', side_effect=responses):
        result = downloader.download('https://twitter.com/user/status/1234567890', max_retries=2)
        assert result

def test_download_media_invalid_url(downloader):
    """测试无效URL。"""
    with pytest.raises(ValueError, match='Invalid tweet URL'):
        downloader.download('invalid_url')

def test_download_media_no_media(downloader, mock_extractor):
    """测试无媒体推文。"""
    tweet_info = {
        'id': '1234567890',
        'text': 'Test tweet without media',
        'author': {'name': 'Test User', 'screen_name': 'testuser'},
        'media': []
    }
    mock_extractor.extract_tweet_info.return_value = tweet_info
    
    with pytest.raises(DownloadError, match='No media found'):
        downloader.download('https://twitter.com/user/status/1234567890')

def test_download_media_partial(downloader, mock_extractor, tweet_info):
    """测试部分媒体下载失败。"""
    mock_extractor.extract_tweet_info.return_value = tweet_info
    
    # 模拟第一个媒体下载成功，第二个失败
    responses = [
        Mock(status_code=200, headers={'content-length': '1024'}, iter_content=Mock(return_value=[b'test data'])),
        Mock(status_code=404, raise_for_status=Mock(side_effect=requests.exceptions.HTTPError('Not found')))
    ]
    
    with patch('requests.get', side_effect=responses):
        result = downloader.download('https://twitter.com/user/status/1234567890')
        assert not result  # 部分失败应该返回False

def test_download_media_with_progress(downloader, mock_extractor, tweet_info):
    """测试带进度回调的下载。"""
    mock_extractor.extract_tweet_info.return_value = tweet_info
    
    # 模拟下载响应
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-length': '1024'}
    mock_response.iter_content.return_value = [b'test data'] * 4
    
    progress_values = []
    def progress_callback(value, message):
        progress_values.append(value)
    
    with patch('requests.get', return_value=mock_response):
        downloader.download(
            'https://twitter.com/user/status/1234567890',
            progress_callback=progress_callback
        )
        assert len(progress_values) > 0
        assert progress_values[-1] == 1.0  # 最后应该达到100%

def test_download_media_with_speed_limit(downloader, mock_extractor, tweet_info):
    """测试速度限制。"""
    mock_extractor.extract_tweet_info.return_value = tweet_info
    
    # 模拟大文件下载
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-length': str(2 * 1024 * 1024)}  # 2MB
    mock_response.iter_content.return_value = [b'x' * 1024] * 2048
    
    start_time = time.time()
    with patch('requests.get', return_value=mock_response):
        downloader.download('https://twitter.com/user/status/1234567890')
    duration = time.time() - start_time
    
    # 由于速度限制为1MB/s，2MB的文件应该至少需要2秒
    assert duration >= 2.0

def test_download_media_concurrent(downloader, mock_extractor):
    """测试并发下载。"""
    # 创建多个媒体文件的推文
    tweet_info = {
        'id': '1234567890',
        'author': {'screen_name': 'testuser'},
        'media': [
            {'type': 'photo', 'url': f'https://example.com/photo{i}.jpg'}
            for i in range(4)
        ]
    }
    mock_extractor.extract_tweet_info.return_value = tweet_info
    
    # 模拟下载响应
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-length': '1024'}
    mock_response.iter_content.return_value = [b'test data']
    
    with patch('requests.get', return_value=mock_response):
        result = downloader.download('https://twitter.com/user/status/1234567890')
        assert result
        
        # 验证所有文件都已下载
        for i in range(4):
            file_path = downloader.config.save_dir / f'testuser_1234567890_photo_{i}.jpg'
            assert file_path.exists()

def test_cleanup_on_error(downloader, mock_extractor, tweet_info):
    """测试错误时的清理。"""
    mock_extractor.extract_tweet_info.return_value = tweet_info
    
    # 模拟下载中断
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-length': '1024'}
    mock_response.iter_content.side_effect = Exception('Download interrupted')
    
    with patch('requests.get', return_value=mock_response):
        with pytest.raises(DownloadError):
            downloader.download('https://twitter.com/user/status/1234567890')
            
        # 验证临时文件已清理
        for media in tweet_info['media']:
            temp_path = downloader.config.save_dir / f"{tweet_info['author']['screen_name']}_{tweet_info['id']}_{media['type']}.part"
            assert not temp_path.exists()

def test_download_media_custom_path(downloader, mock_extractor, tweet_info):
    """测试自定义保存路径。"""
    mock_extractor.extract_tweet_info.return_value = tweet_info
    
    # 模拟下载响应
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'content-length': '1024'}
    mock_response.iter_content.return_value = [b'test data']
    
    custom_path = downloader.config.save_dir / 'custom' / 'path'
    with patch('requests.get', return_value=mock_response):
        result = downloader.download(
            'https://twitter.com/user/status/1234567890',
            save_dir=custom_path
        )
        assert result
        
        # 验证文件保存在自定义路径
        for media in tweet_info['media']:
            file_path = custom_path / f"{tweet_info['author']['screen_name']}_{tweet_info['id']}_{media['type']}"
            assert file_path.exists()

def test_config_validation(tmp_path):
    """测试配置验证。"""
    # 测试有效配置
    config = TwitterDownloaderConfig(save_dir=tmp_path)
    assert config.filename_template == "{author}/{tweet_id}/{media_type}_{index}{ext}"
    assert config.max_concurrent_downloads == 3
    
    # 测试文件名模板验证
    assert config.validate_template("{author}_{tweet_id}_{ext}")
    assert config.validate_template("{date}/{author}/{media_type}_{index}")
    assert not config.validate_template("{invalid}_{ext}")

@pytest.mark.asyncio
async def test_speed_limiter():
    """测试速度限制器。"""
    limit = 1024  # 1KB/s
    limiter = SpeedLimiter(limit)
    
    # 测试单次传输
    start = asyncio.get_event_loop().time()
    await limiter.wait(limit)  # 应该立即返回
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 0.1
    
    # 测试速度限制
    start = asyncio.get_event_loop().time()
    await limiter.wait(limit * 2)  # 应该等待约1秒
    elapsed = asyncio.get_event_loop().time() - start
    assert 0.9 < elapsed < 1.1
    
    # 测试当前速度计算
    assert 0 < limiter.current_speed <= limit * 1.1

@pytest.mark.asyncio
async def test_download_media(downloader, tmp_path):
    """测试媒体下载。"""
    # 模拟响应数据
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"content-length": "1024"}
    mock_response.content.iter_chunked = AsyncMock(
        return_value=[b"x" * 512, b"x" * 512]
    )
    
    # 模拟会话
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_response
    
    # 模拟客户端会话
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_session
    
    with patch("aiohttp.ClientSession", return_value=mock_client):
        # 测试成功下载
        result = await downloader._download_media(
            "https://example.com/test.jpg",
            tmp_path / "test.jpg",
            "photo"
        )
        assert result is True
        assert (tmp_path / "test.jpg").exists()
        assert (tmp_path / "test.jpg").stat().st_size == 1024
        
        # 测试下载失败
        mock_response.status = 404
        result = await downloader._download_media(
            "https://example.com/not_found.jpg",
            tmp_path / "not_found.jpg",
            "photo"
        )
        assert result is False
        assert not (tmp_path / "not_found.jpg").exists()

@pytest.mark.asyncio
async def test_download_all_from_user(downloader, tmp_path, mock_extractor):
    """测试用户媒体下载。"""
    # 模拟GraphQL响应
    mock_response = {
        "data": {
            "user": {
                "media": {
                    "edges": [
                        {
                            "node": {
                                "id": "123",
                                "createdAt": "2024-01-01T12:00:00Z",
                                "text": "Test tweet",
                                "author": {"username": "test_user"},
                                "mediaItems": [
                                    {
                                        "type": "PHOTO",
                                        "url": "https://example.com/1.jpg",
                                        "width": 800,
                                        "height": 600,
                                        "quality": "high"
                                    }
                                ],
                                "stats": {
                                    "likes": 100,
                                    "retweets": 50
                                }
                            }
                        }
                    ],
                    "pageInfo": {
                        "hasNextPage": False,
                        "endCursor": None
                    }
                }
            }
        }
    }
    
    # 模拟用户ID获取
    with patch.object(downloader, "_get_user_id",
                     new_callable=AsyncMock) as mock_get_id:
        mock_get_id.return_value = "user123"
        
        # 模拟GraphQL请求
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response)
        mock_session.__aenter__.return_value = mock_response
        
        with patch("aiohttp.ClientSession", return_value=mock_session):
            # 模拟媒体下载
            with patch.object(downloader, "_download_media",
                            new_callable=AsyncMock) as mock_download:
                mock_download.return_value = True
                
                # 测试下载
                result = await downloader.download_all_from_user("test_user", max_items=1)
                assert result is True
                
                # 验证调用
                mock_get_id.assert_called_once_with("test_user")
                assert mock_download.call_count == 1

@pytest.mark.asyncio
async def test_download_tweet(downloader, tmp_path, mock_extractor):
    """测试推文下载。"""
    # 模拟推文信息
    tweet_info = {
        "id": "123456",
        "author": "test_user",
        "created_at": "2024-01-01T12:00:00Z",
        "text": "Test tweet",
        "likes": 100,
        "reposts": 50,
        "media_urls": [
            "https://example.com/photo.jpg",
            "https://example.com/video.mp4"
        ]
    }
    
    # 设置模拟提取器
    mock_extractor.extract_info.return_value = tweet_info
    
    # 模拟媒体下载
    with patch.object(downloader, "_download_media",
                     new_callable=AsyncMock) as mock_download:
        mock_download.return_value = True
        
        # 测试下载
        result = await downloader.download("https://twitter.com/test/123456")
        assert result is True
        
        # 验证调用
        assert mock_download.call_count == 2
        
        # 验证文件路径
        calls = mock_download.call_args_list
        assert "photo_1.jpg" in str(calls[0][0][1])
        assert "video_2.mp4" in str(calls[1][0][1])

def test_get_video_info(downloader, mock_extractor):
    """测试获取视频信息。"""
    # 模拟推文信息
    tweet_info = {
        "id": "123456",
        "author": "test_user",
        "created_at": "2024-01-01T12:00:00Z",
        "text": "Test video",
        "likes": 100,
        "reposts": 50,
        "quality": "1080p",
        "media_urls": [
            "https://example.com/video.mp4",
            "https://example.com/thumbnail.jpg"
        ]
    }
    
    # 设置模拟提取器
    mock_extractor.extract_info.return_value = tweet_info
    
    # 测试成功获取视频信息
    info = downloader.get_video_info("https://twitter.com/test/123456")
    assert info["title"] == "Test video"
    assert info["author"] == "test_user"
    assert info["quality"] == "1080p"
    
    # 测试无视频内容
    tweet_info["media_urls"] = ["https://example.com/photo.jpg"]
    mock_extractor.extract_info.return_value = tweet_info
    
    with pytest.raises(ValueError, match="未找到视频内容"):
        downloader.get_video_info("https://twitter.com/test/123456")
        
    # 测试提取失败
    mock_extractor.extract_info.side_effect = Exception("提取失败")
    
    with pytest.raises(ValueError, match="获取视频信息失败"):
        downloader.get_video_info("https://twitter.com/test/123456")

def test_cancel_download(downloader):
    """测试取消下载。"""
    assert not downloader.is_canceled
    downloader.cancel()
    assert downloader.is_canceled 