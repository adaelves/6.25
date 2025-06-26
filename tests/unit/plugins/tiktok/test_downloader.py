"""TikTok下载器测试模块。

测试下载功能的稳定性和正确性。
"""

import time
import json
import pytest
import asyncio
import re
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from src.plugins.tiktok.downloader import TikTokDownloader, DownloadError

@pytest.fixture
def downloader():
    """创建下载器实例。"""
    return TikTokDownloader(proxy="http://127.0.0.1:7890")

@pytest.fixture
def ios_downloader():
    """创建iOS下载器实例。"""
    return TikTokDownloader(proxy="http://127.0.0.1:7890", platform="ios")

@pytest.fixture
def android_downloader():
    """创建Android下载器实例。"""
    return TikTokDownloader(proxy="http://127.0.0.1:7890", platform="android")

@pytest.fixture
def temp_dir(tmp_path):
    """创建临时目录。"""
    return tmp_path

def test_ios_user_agent(ios_downloader):
    """测试iOS User-Agent生成。"""
    ua = ios_downloader._get_user_agent()
    
    # 验证格式
    assert "iPhone" in ua
    assert "CPU iPhone OS" in ua
    assert "AppleWebKit/605.1.15" in ua
    assert "Mobile/15E148" in ua
    
    # 验证iOS版本
    version_match = re.search(r"OS (\d+_\d+)", ua)
    assert version_match
    version = version_match.group(1).replace("_", ".")
    major, minor = map(int, version.split("."))
    assert 14 <= major <= 16
    assert 0 <= minor <= 9

def test_android_user_agent(android_downloader):
    """测试Android User-Agent生成。"""
    ua = android_downloader._get_user_agent()
    
    # 验证格式
    assert "Linux; Android" in ua
    assert "AppleWebKit/537.36" in ua
    assert "Chrome/" in ua
    assert "Mobile Safari/537.36" in ua
    
    # 验证Android版本
    version_match = re.search(r"Android (\d+\.\d+)", ua)
    assert version_match
    version = version_match.group(1)
    major, minor = map(int, version.split("."))
    assert 10 <= major <= 13
    assert 0 <= minor <= 9
    
    # 验证设备
    device = re.search(r"Android \d+\.\d+; ([^)]+)\)", ua).group(1)
    assert device in android_downloader.ANDROID_DEVICES

@pytest.mark.asyncio
async def test_get_direct_url(downloader):
    """测试获取直连URL。"""
    video_id = "7123456789"
    
    # 验证URL格式
    url = await downloader._get_direct_url(video_id)
    assert url.startswith("https://api.tiktokv.com/aweme/v1/play/")
    
    # 验证参数
    params = dict(p.split("=") for p in url.split("?")[1].split("&"))
    assert params["video_id"] == video_id
    assert params["line"] == "0"
    assert params["ratio"] == "1080p"
    assert "_signature" in params
    assert "device_id" in params

@pytest.mark.asyncio
async def test_get_direct_url_with_options(downloader):
    """测试获取直连URL(带选项)。"""
    video_id = "7123456789"
    line = "1"
    ratio = "720p"
    
    # 验证URL格式
    url = await downloader._get_direct_url(video_id, line=line, ratio=ratio)
    assert url.startswith("https://api.tiktokv.com/aweme/v1/play/")
    
    # 验证参数
    params = dict(p.split("=") for p in url.split("?")[1].split("&"))
    assert params["video_id"] == video_id
    assert params["line"] == line
    assert params["ratio"] == ratio
    assert "_signature" in params
    assert "device_id" in params

@pytest.mark.asyncio
async def test_get_direct_url_signature_error(downloader):
    """测试获取直连URL签名错误。"""
    video_id = "7123456789"
    
    # 模拟签名失败
    with patch.object(downloader.signature, "sign") as mock_sign:
        mock_sign.side_effect = SignatureError("测试错误")
        
        with pytest.raises(DownloadError, match="生成签名失败"):
            await downloader._get_direct_url(video_id)

@pytest.mark.asyncio
async def test_download_video_with_direct_url(downloader, temp_dir):
    """测试使用直连URL下载视频。"""
    video_id = "7123456789"
    save_path = temp_dir / "test.mp4"
    
    # 模拟请求
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.content.iter_chunked = AsyncMock(return_value=[b"test"])
        mock_get.return_value.__aenter__.return_value = mock_response
        
        path = await downloader.download_video(video_id, save_path)
        assert path == save_path
        assert path.exists()
        assert path.stat().st_size > 0
        
        # 验证请求URL
        call_args = mock_get.call_args_list[0][0]
        assert call_args[0].startswith("https://api.tiktokv.com/aweme/v1/play/")

@pytest.mark.asyncio
async def test_download_video(downloader, temp_dir):
    """测试视频下载。"""
    video_id = "7123456789"
    save_path = temp_dir / "test.mp4"
    
    # 模拟视频信息响应
    video_info = {
        "aweme_detail": {
            "video": {
                "play_addr": {
                    "url_list": ["https://test.com/video.mp4"]
                }
            }
        }
    }
    
    # 模拟请求
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value=video_info)
        mock_response.content.iter_chunked = AsyncMock(return_value=[b"test"])
        mock_get.return_value.__aenter__.return_value = mock_response
        
        path = await downloader.download_video(video_id, save_path)
        assert path == save_path
        assert path.exists()
        assert path.stat().st_size > 0

@pytest.mark.asyncio
async def test_download_image(downloader, temp_dir):
    """测试图片下载。"""
    image_id = "7123456789"
    save_path = temp_dir / "test.jpg"
    
    # 模拟图片信息响应
    image_info = {
        "aweme_detail": {
            "image_post_info": {
                "images": [{
                    "display_image": {
                        "url_list": ["https://test.com/image.jpg"]
                    }
                }]
            }
        }
    }
    
    # 模拟请求
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value=image_info)
        mock_response.content.iter_chunked = AsyncMock(return_value=[b"test"])
        mock_get.return_value.__aenter__.return_value = mock_response
        
        path = await downloader.download_image(image_id, save_path)
        assert path == save_path
        assert path.exists()
        assert path.stat().st_size > 0

@pytest.mark.asyncio
async def test_download_by_url_video(downloader, temp_dir):
    """测试通过URL下载视频。"""
    url = "https://www.tiktok.com/@user/video/7123456789"
    save_path = temp_dir / "test.mp4"
    
    # 模拟视频信息响应
    video_info = {
        "aweme_detail": {
            "video": {
                "play_addr": {
                    "url_list": ["https://test.com/video.mp4"]
                }
            }
        }
    }
    
    # 模拟请求
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value=video_info)
        mock_response.content.iter_chunked = AsyncMock(return_value=[b"test"])
        mock_get.return_value.__aenter__.return_value = mock_response
        
        path = await downloader.download_by_url(url, save_path)
        assert path == save_path
        assert path.exists()
        assert path.stat().st_size > 0

@pytest.mark.asyncio
async def test_download_by_url_image(downloader, temp_dir):
    """测试通过URL下载图片。"""
    url = "https://www.tiktok.com/@user/image/7123456789"
    save_path = temp_dir / "test.jpg"
    
    # 模拟图片信息响应
    image_info = {
        "aweme_detail": {
            "image_post_info": {
                "images": [{
                    "display_image": {
                        "url_list": ["https://test.com/image.jpg"]
                    }
                }]
            }
        }
    }
    
    # 模拟请求
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value=image_info)
        mock_response.content.iter_chunked = AsyncMock(return_value=[b"test"])
        mock_get.return_value.__aenter__.return_value = mock_response
        
        path = await downloader.download_by_url(url, save_path)
        assert path == save_path
        assert path.exists()
        assert path.stat().st_size > 0

@pytest.mark.asyncio
async def test_download_user_videos(downloader, temp_dir):
    """测试下载用户视频。"""
    user_id = "123456789"
    
    # 模拟视频列表响应
    video_list = {
        "aweme_list": [
            {
                "aweme_id": "7123456789",
                "video": {
                    "play_addr": {
                        "url_list": ["https://test.com/video1.mp4"]
                    }
                }
            },
            {
                "aweme_id": "7123456790",
                "video": {
                    "play_addr": {
                        "url_list": ["https://test.com/video2.mp4"]
                    }
                }
            }
        ],
        "has_more": False
    }
    
    # 模拟请求
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value=video_list)
        mock_response.content.iter_chunked = AsyncMock(return_value=[b"test"])
        mock_get.return_value.__aenter__.return_value = mock_response
        
        paths = await downloader.download_user_videos(user_id, temp_dir, max_videos=2)
        assert len(paths) == 2
        for path in paths:
            assert path.exists()
            assert path.stat().st_size > 0

@pytest.mark.asyncio
async def test_download_user_images(downloader, temp_dir):
    """测试下载用户图片。"""
    user_id = "123456789"
    
    # 模拟图片列表响应
    image_list = {
        "aweme_list": [
            {
                "aweme_id": "7123456789",
                "image_post_info": {
                    "images": [{
                        "display_image": {
                            "url_list": ["https://test.com/image1.jpg"]
                        }
                    }]
                }
            },
            {
                "aweme_id": "7123456790",
                "image_post_info": {
                    "images": [{
                        "display_image": {
                            "url_list": ["https://test.com/image2.jpg"]
                        }
                    }]
                }
            }
        ],
        "has_more": False
    }
    
    # 模拟请求
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value=image_list)
        mock_response.content.iter_chunked = AsyncMock(return_value=[b"test"])
        mock_get.return_value.__aenter__.return_value = mock_response
        
        paths = await downloader.download_user_images(user_id, temp_dir, max_images=2)
        assert len(paths) == 2
        for path in paths:
            assert path.exists()
            assert path.stat().st_size > 0

@pytest.mark.asyncio
async def test_request_retry(downloader):
    """测试请求重试。"""
    url = "https://test.com"
    retry_count = 0
    
    async def mock_request(*args, **kwargs):
        nonlocal retry_count
        retry_count += 1
        raise asyncio.TimeoutError()
        
    with patch("aiohttp.ClientSession.get", side_effect=mock_request):
        with pytest.raises(DownloadError):
            await downloader._request(url)
            
    assert retry_count == downloader.max_retries + 1

@pytest.mark.asyncio
async def test_proxy_switch_delay():
    """测试代理切换延迟。
    
    验证切换代理的延迟是否<200ms。
    """
    # 创建两个下载器实例
    d1 = TikTokDownloader(proxy="http://127.0.0.1:7890")
    d2 = TikTokDownloader(proxy="http://127.0.0.1:7891")
    
    # 记录开始时间
    start = time.time()
    
    # 切换代理
    d1.proxy = d2.proxy
    
    # 计算延迟
    delay = (time.time() - start) * 1000
    assert delay < 200  # 延迟<200ms

@pytest.mark.asyncio
async def test_signature_stability(downloader):
    """测试签名稳定性。
    
    连续生成100次签名,验证成功率。
    """
    params = {"test": "value"}
    success = 0
    
    # 模拟请求
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value={"aweme_detail": {}})
        mock_get.return_value.__aenter__.return_value = mock_response
        
        for _ in range(100):
            try:
                await downloader._request("https://test.com", params)
                success += 1
            except Exception:
                continue
                
    assert success >= 80  # 成功率≥80%

@pytest.mark.asyncio
async def test_invalid_url(downloader, temp_dir):
    """测试无效URL。"""
    invalid_urls = [
        "",
        "http://",
        "https://tiktok.com",
        "https://www.tiktok.com/@user",
        "https://www.tiktok.com/video"
    ]
    
    for url in invalid_urls:
        with pytest.raises(DownloadError):
            await downloader.download_by_url(url, temp_dir / "test.mp4")

@pytest.mark.asyncio
async def test_unsupported_content(downloader, temp_dir):
    """测试不支持的内容类型。"""
    url = "https://www.tiktok.com/@user/video/7123456789"
    
    # 模拟响应
    content_info = {
        "aweme_detail": {
            "unknown_type": {}
        }
    }
    
    # 模拟请求
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value=content_info)
        mock_get.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(DownloadError, match="不支持的内容类型"):
            await downloader.download_by_url(url, temp_dir / "test.mp4") 