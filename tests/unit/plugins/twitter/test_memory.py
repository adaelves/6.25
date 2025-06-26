"""Twitter下载器内存泄漏测试。"""

import os
import gc
import asyncio
import pytest
import psutil
import logging
from pathlib import Path
from typing import Generator

from src.plugins.twitter.downloader import TwitterDownloader
from src.plugins.twitter.config import TwitterDownloaderConfig

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
def config() -> TwitterDownloaderConfig:
    """创建测试配置。"""
    save_dir = Path("./downloads").absolute()
    save_dir.mkdir(parents=True, exist_ok=True)
    
    return TwitterDownloaderConfig(
        save_dir=save_dir,
        proxy="127.0.0.1:7890",
        timeout=30,
        max_retries=3,
        chunk_size=8192,
        max_concurrent_downloads=3,
        speed_limit=0,
        custom_headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    )

def get_memory_usage() -> float:
    """获取当前进程的内存使用量（MB）。"""
    process = psutil.Process(os.getpid())
    memory = process.memory_info().rss / 1024 / 1024
    logger.info(f"当前内存使用量: {memory:.2f}MB")
    return memory

@pytest.mark.asyncio
async def test_no_memory_leak_after_multiple_downloads(config: TwitterDownloaderConfig):
    """测试多次下载后是否存在内存泄漏。"""
    logger.info("开始内存泄漏测试...")
    
    # 初始内存使用量
    gc.collect()  # 强制垃圾回收
    initial_memory = get_memory_usage()
    logger.info(f"初始内存使用量: {initial_memory:.2f}MB")
    
    # 创建下载器并执行多次下载
    test_urls = [
        "https://twitter.com/user1/status/123456789",
        "https://twitter.com/user2/status/987654321",
        "https://twitter.com/user3/status/456789123"
    ]
    
    async with TwitterDownloader(config) as downloader:
        for i, url in enumerate(test_urls, 1):
            logger.info(f"测试下载 {i}/{len(test_urls)}: {url}")
            try:
                await downloader.download(url)
            except Exception as e:
                logger.error(f"下载出错（预期内）: {e}")
                
    # 等待一段时间确保资源释放
    logger.info("等待资源释放...")
    await asyncio.sleep(1)
    gc.collect()  # 强制垃圾回收
    
    # 检查内存使用量
    final_memory = get_memory_usage()
    memory_diff = final_memory - initial_memory
    logger.info(f"最终内存使用量: {final_memory:.2f}MB")
    logger.info(f"内存差异: {memory_diff:.2f}MB")
    
    # 允许有少量的内存增长（比如Python的内部缓存等）
    assert memory_diff < 50, f"内存泄漏检测：使用量增加了 {memory_diff:.2f}MB"
    
@pytest.mark.asyncio
async def test_browser_cleanup_on_error(config: TwitterDownloaderConfig):
    """测试错误情况下的浏览器资源清理。"""
    logger.info("开始测试错误情况下的资源清理...")
    downloader = TwitterDownloader(config)
    
    try:
        # 触发一个错误
        await downloader.download("invalid_url")
    except Exception as e:
        logger.info(f"预期的错误: {e}")
    finally:
        await downloader.close()
        
    # 检查浏览器实例是否被正确清理
    assert downloader._browser is None, "浏览器实例未被清理"
    assert downloader._context is None, "浏览器上下文未被清理"
    logger.info("资源清理测试通过")
    
@pytest.mark.asyncio
async def test_concurrent_browser_initialization(config: TwitterDownloaderConfig):
    """测试并发初始化浏览器的情况。"""
    logger.info("开始测试并发初始化...")
    
    async def download_task(downloader: TwitterDownloader, url: str):
        try:
            await downloader.download(url)
        except Exception as e:
            logger.error(f"下载出错（预期内）: {e}")
            
    downloader = TwitterDownloader(config)
    
    try:
        # 同时启动多个下载任务
        tasks = [
            download_task(downloader, f"https://twitter.com/user{i}/status/{i}")
            for i in range(3)  # 减少测试数量以加快测试速度
        ]
        
        logger.info(f"启动 {len(tasks)} 个并发任务")
        await asyncio.gather(*tasks)
        
        # 检查是否只创建了一个浏览器实例
        assert downloader._browser is not None, "浏览器实例未创建"
        browser_id = id(downloader._browser)
        logger.info(f"浏览器实例ID: {browser_id}")
        
        # 再次执行下载任务
        logger.info("执行额外的下载任务")
        await download_task(downloader, "https://twitter.com/user/status/123")
        
        # 验证使用的是同一个浏览器实例
        assert id(downloader._browser) == browser_id, "创建了新的浏览器实例"
        logger.info("浏览器实例复用测试通过")
        
    finally:
        # 清理资源
        await downloader.close()
        logger.info("资源已清理")
    
@pytest.mark.asyncio
async def test_context_manager_cleanup(config: TwitterDownloaderConfig):
    """测试上下文管理器的资源清理。"""
    logger.info("开始测试上下文管理器...")
    
    async with TwitterDownloader(config) as downloader:
        # 执行一些操作以初始化浏览器
        try:
            await downloader.download("https://twitter.com/user/status/123")
        except Exception as e:
            logger.error(f"下载出错（预期内）: {e}")
            
    # 验证资源已被清理
    assert downloader._browser is None, "浏览器实例未被上下文管理器清理"
    assert downloader._context is None, "浏览器上下文未被上下文管理器清理"
    logger.info("上下文管理器测试通过") 