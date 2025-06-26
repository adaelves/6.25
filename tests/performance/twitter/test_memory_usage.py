"""Twitter 下载器测试脚本。

测试大型视频下载的内存占用和性能。
"""

import asyncio
import logging
import psutil
import os
from pathlib import Path
from datetime import datetime

from src.plugins.twitter.downloader import TwitterDownloader
from src.plugins.twitter.config import TwitterDownloaderConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_memory_usage():
    """获取当前进程的内存使用情况。"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # 转换为MB

async def test_download():
    """测试视频下载。"""
    # 记录初始内存
    initial_memory = get_memory_usage()
    logger.info(f"初始内存使用: {initial_memory:.2f} MB")
    
    # 创建下载配置
    config = TwitterDownloaderConfig(
        save_dir=Path("downloads"),
        proxy="http://127.0.0.1:7890",  # 使用配置的代理
        chunk_size=8192,  # 8KB 块大小
        max_retries=3,
        api_token="AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        custom_headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://twitter.com/",
            "Origin": "https://twitter.com"
        }
    )
    
    # 进度回调
    def progress_callback(progress: float, status: str):
        memory = get_memory_usage()
        logger.info(
            f"进度: {progress*100:.1f}% - {status} - "
            f"内存使用: {memory:.2f} MB"
        )
    
    # 创建下载器
    downloader = TwitterDownloader(
        config=config,
        progress_callback=progress_callback
    )
    
    try:
        # 测试视频URL - SpaceX 的一个视频推文
        video_url = "https://twitter.com/SpaceX/status/1673883852705406976"
        
        # 开始下载
        start_time = datetime.now()
        success = await downloader.download(video_url)
        end_time = datetime.now()
        
        # 记录最终内存
        final_memory = get_memory_usage()
        duration = (end_time - start_time).total_seconds()
        
        # 输出结果
        logger.info(f"下载{'成功' if success else '失败'}")
        logger.info(f"耗时: {duration:.2f} 秒")
        logger.info(f"最终内存使用: {final_memory:.2f} MB")
        logger.info(f"内存增长: {final_memory - initial_memory:.2f} MB")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_download()) 