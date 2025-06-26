"""下载调度器测试模块。

测试优先级队列和并发控制功能。
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from src.services.scheduler import DownloadScheduler, DownloadTask

@pytest.fixture
def scheduler():
    """创建调度器实例。"""
    return DownloadScheduler(max_concurrent=2)

def test_add_task(scheduler):
    """测试添加任务。"""
    url = "https://test.com/video.mp4"
    
    # 添加任务
    task = scheduler.add_task(url, priority=1)
    
    # 验证任务信息
    assert task.url == url
    assert task.priority == 1
    assert task.status == "pending"
    assert task.create_time <= datetime.now()
    assert task.start_time is None
    assert task.end_time is None
    assert task.error is None
    
    # 验证队列
    next_task = scheduler.get_next_task()
    assert next_task == task

def test_add_task_invalid_priority(scheduler):
    """测试添加无效优先级任务。"""
    url = "https://test.com/video.mp4"
    
    with pytest.raises(ValueError, match="无效的优先级"):
        scheduler.add_task(url, priority=3)

def test_priority_order(scheduler):
    """测试优先级顺序。"""
    urls = [
        "https://test.com/1.mp4",
        "https://test.com/2.mp4",
        "https://test.com/3.mp4"
    ]
    
    # 添加不同优先级的任务
    scheduler.add_task(urls[0], priority=2)  # 后台
    scheduler.add_task(urls[1], priority=0)  # 最高
    scheduler.add_task(urls[2], priority=1)  # 普通
    
    # 验证顺序
    task1 = scheduler.get_next_task()
    assert task1.url == urls[1]  # 最高优先级
    
    task2 = scheduler.get_next_task()
    assert task2.url == urls[2]  # 普通优先级
    
    task3 = scheduler.get_next_task()
    assert task3.url == urls[0]  # 后台优先级

def test_get_task(scheduler):
    """测试获取任务。"""
    url = "https://test.com/video.mp4"
    
    # 添加任务
    task = scheduler.add_task(url)
    
    # 获取任务
    assert scheduler.get_task(url) == task
    assert scheduler.get_task("not_exists") is None

@pytest.mark.asyncio
async def test_run_task(scheduler):
    """测试运行任务。"""
    url = "https://test.com/video.mp4"
    task = scheduler.add_task(url)
    
    # 模拟下载函数
    download_func = AsyncMock()
    
    # 运行任务
    await scheduler.run_task(task, download_func)
    
    # 验证状态
    assert task.status == "completed"
    assert task.start_time is not None
    assert task.end_time is not None
    assert task.error is None
    
    # 验证下载函数调用
    download_func.assert_called_once_with(url)

@pytest.mark.asyncio
async def test_run_task_error(scheduler):
    """测试运行任务失败。"""
    url = "https://test.com/video.mp4"
    task = scheduler.add_task(url)
    
    # 模拟下载函数
    async def download_func(_):
        raise Exception("下载失败")
        
    # 运行任务
    await scheduler.run_task(task, download_func)
    
    # 验证状态
    assert task.status == "failed"
    assert task.start_time is not None
    assert task.end_time is not None
    assert task.error == "下载失败"

@pytest.mark.asyncio
async def test_concurrent_limit(scheduler):
    """测试并发限制。"""
    urls = [
        "https://test.com/1.mp4",
        "https://test.com/2.mp4",
        "https://test.com/3.mp4"
    ]
    
    # 添加任务
    tasks = [scheduler.add_task(url) for url in urls]
    
    # 模拟下载函数
    async def download_func(_):
        await asyncio.sleep(0.1)
        
    # 运行任务
    start_time = datetime.now()
    
    await asyncio.gather(*[
        scheduler.run_task(task, download_func)
        for task in tasks
    ])
    
    duration = datetime.now() - start_time
    
    # 验证执行时间(应该分两批运行)
    assert duration >= timedelta(seconds=0.2)

def test_get_stats(scheduler):
    """测试获取统计信息。"""
    # 添加任务
    task1 = scheduler.add_task("https://test.com/1.mp4")
    task2 = scheduler.add_task("https://test.com/2.mp4")
    task3 = scheduler.add_task("https://test.com/3.mp4")
    
    # 修改状态
    task1.status = "running"
    task2.status = "completed"
    task3.status = "failed"
    
    # 验证统计
    stats = scheduler.get_stats()
    assert stats["pending"] == 0
    assert stats["running"] == 1
    assert stats["completed"] == 1
    assert stats["failed"] == 1

@pytest.mark.asyncio
async def test_empty_queue(scheduler):
    """测试空队列。"""
    assert scheduler.get_next_task() is None
    
    # 模拟下载函数
    download_func = AsyncMock()
    
    # 运行一段时间
    try:
        await asyncio.wait_for(
            scheduler.run(download_func),
            timeout=0.1
        )
    except asyncio.TimeoutError:
        pass
        
    # 验证下载函数未被调用
    download_func.assert_not_called() 