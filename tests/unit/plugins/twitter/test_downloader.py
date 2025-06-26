"""Twitter下载器测试模块。"""

import os
import json
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from src.plugins.twitter.config import TwitterDownloaderConfig
from src.plugins.twitter.downloader import TwitterDownloader, SpeedLimiter

@pytest.fixture
def config(tmp_path):
    """创建测试配置。"""
    return TwitterDownloaderConfig(
        save_dir=tmp_path,
        filename_template="{author}/{tweet_id}/{media_type}_{index}{ext}",
        max_concurrent_downloads=2,
        speed_limit=1024 * 1024,  # 1MB/s
        chunk_size=8192,
        max_retries=2,
        proxy="http://127.0.0.1:7890",
        timeout=5.0,
        api_token="test_token"
    )

@pytest.fixture
def mock_extractor():
    """创建模拟的提取器。"""
    with patch("src.plugins.twitter.downloader.TwitterExtractor") as mock:
        yield mock.return_value

@pytest.fixture
def downloader(config, mock_extractor):
    """创建测试下载器。"""
    return TwitterDownloader(config)

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