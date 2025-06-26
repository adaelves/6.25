import asyncio
import logging
from pathlib import Path
from src.plugins.twitter.downloader import TwitterDownloader
from src.plugins.twitter.config import TwitterDownloaderConfig

# 配置日志
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_download():
    # 配置下载器
    config = TwitterDownloaderConfig(
        save_dir=Path("downloads"),
        proxy="http://127.0.0.1:7890",  # 设置代理
        timeout=30,
        max_retries=3,
        chunk_size=1024 * 1024,  # 1MB
        max_concurrent_downloads=2,
        custom_headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    
    # 创建下载器
    downloader = TwitterDownloader(config)
    
    # 测试链接
    urls = [
        "https://twitter.com/RonaldMorg3069/status/1938026237114429819",
        "https://twitter.com/keith_md16717/status/1938026947776291155"
    ]
    
    # 下载所有视频
    for url in urls:
        try:
            print(f"\n开始下载: {url}")
            success = await downloader.download(url)
            print(f"下载{'成功' if success else '失败'}: {url}")
        except Exception as e:
            print(f"下载出错: {url}\n错误: {e}")

if __name__ == "__main__":
    # 创建下载目录
    Path("downloads").mkdir(exist_ok=True)
    
    # 运行测试
    asyncio.run(test_download()) 