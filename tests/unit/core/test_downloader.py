"""基础下载器测试模块。

测试代理支持和超时重试功能。
"""

import pytest
import responses
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.downloader import BaseDownloader, DownloadError

@pytest.fixture
def downloader():
    """创建下载器实例。"""
    return BaseDownloader(
        save_dir="downloads",
        proxy="http://127.0.0.1:7890",
        timeout=5,
        max_retries=2
    )

@pytest.fixture
def mock_session():
    """模拟requests.Session。"""
    with patch("requests.Session") as mock:
        yield mock

def test_init_with_proxy(mock_session):
    """测试使用代理初始化。"""
    proxy = "http://127.0.0.1:7890"
    downloader = BaseDownloader(save_dir="downloads", proxy=proxy)
    
    # 验证代理配置
    session = mock_session.return_value
    assert session.proxies == {
        "http": proxy,
        "https": proxy
    }

def test_init_without_proxy(mock_session):
    """测试不使用代理初始化。"""
    downloader = BaseDownloader(save_dir="downloads")
    
    # 验证代理配置
    session = mock_session.return_value
    assert not session.proxies

@responses.activate
def test_download_success(downloader, tmp_path):
    """测试下载成功。"""
    # 准备测试数据
    url = "https://example.com/test.mp4"
    save_path = tmp_path / "test.mp4"
    content = b"test content"
    
    # 模拟响应
    responses.add(
        responses.GET,
        url,
        body=content,
        status=200,
        stream=True
    )
    
    # 执行下载
    success = downloader.download(url, save_path)
    
    # 验证结果
    assert success
    assert save_path.exists()
    assert save_path.read_bytes() == content

@responses.activate
def test_download_retry(downloader, tmp_path):
    """测试下载重试。"""
    # 准备测试数据
    url = "https://example.com/test.mp4"
    save_path = tmp_path / "test.mp4"
    content = b"test content"
    
    # 模拟失败然后成功
    responses.add(
        responses.GET,
        url,
        status=503
    )
    responses.add(
        responses.GET,
        url,
        body=content,
        status=200,
        stream=True
    )
    
    # 执行下载
    success = downloader.download(url, save_path)
    
    # 验证结果
    assert success
    assert save_path.exists()
    assert save_path.read_bytes() == content

@responses.activate
def test_download_timeout(downloader, tmp_path):
    """测试下载超时。"""
    # 准备测试数据
    url = "https://example.com/test.mp4"
    save_path = tmp_path / "test.mp4"
    
    # 模拟超时
    responses.add(
        responses.GET,
        url,
        body=requests.Timeout()
    )
    
    # 验证异常
    with pytest.raises(DownloadError, match="下载超时"):
        downloader.download(url, save_path)
        
    # 验证文件未创建
    assert not save_path.exists()

@responses.activate
def test_download_error(downloader, tmp_path):
    """测试下载错误。"""
    # 准备测试数据
    url = "https://example.com/test.mp4"
    save_path = tmp_path / "test.mp4"
    
    # 模拟错误
    responses.add(
        responses.GET,
        url,
        status=404
    )
    
    # 验证异常
    with pytest.raises(DownloadError, match="下载失败"):
        downloader.download(url, save_path)
        
    # 验证文件未创建
    assert not save_path.exists()

def test_close(mock_session):
    """测试关闭下载器。"""
    downloader = BaseDownloader(save_dir="downloads")
    downloader.close()
    
    # 验证会话关闭
    session = mock_session.return_value
    session.close.assert_called_once() 