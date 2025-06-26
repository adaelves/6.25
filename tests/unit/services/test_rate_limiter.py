"""速率限制器测试模块。"""

import time
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from src.services.rate_limiter import RateLimiter, RateLimitExceededError

@pytest.fixture
def limiter():
    """创建测试用速率限制器。"""
    return RateLimiter(calls_per_minute=60)  # 每秒一次调用

@pytest.fixture
def strict_limiter():
    """创建严格模式的速率限制器。"""
    return RateLimiter(calls_per_minute=60, error_on_exceed=True)

def test_init_validation():
    """测试初始化参数验证。"""
    # 有效参数
    limiter = RateLimiter(calls_per_minute=60)
    assert limiter.interval == 1.0  # 每秒一次
    
    # 无效参数
    with pytest.raises(ValueError):
        RateLimiter(calls_per_minute=0)
    with pytest.raises(ValueError):
        RateLimiter(calls_per_minute=-1)

@patch('time.time')
def test_wait_no_delay(mock_time):
    """测试无需等待的情况。"""
    mock_time.return_value = 1000.0
    limiter = RateLimiter(calls_per_minute=60)
    
    # 第一次调用无需等待
    limiter.wait()
    assert limiter.stats["total_wait_time"] == 0
    assert limiter.stats["total_calls"] == 1

@patch('time.time')
@patch('time.sleep')
def test_wait_with_delay(mock_sleep, mock_time):
    """测试需要等待的情况。"""
    mock_time.side_effect = [1000.0, 1000.2, 1000.2]  # 初始化，检查时间，更新时间
    limiter = RateLimiter(calls_per_minute=60)  # 每秒一次
    
    limiter.wait()  # 第一次调用
    mock_time.side_effect = [1000.2, 1000.2, 1000.2]  # 0.2秒后再次调用
    limiter.wait()  # 第二次调用
    
    # 验证等待时间
    mock_sleep.assert_called_once_with(0.8)  # 应该等待0.8秒
    assert limiter.stats["total_calls"] == 2
    assert limiter.stats["total_wait_time"] == 0.8

@patch('time.time')
def test_error_on_exceed(mock_time):
    """测试超出限制时抛出异常。"""
    mock_time.side_effect = [1000.0, 1000.2, 1000.2]
    limiter = RateLimiter(calls_per_minute=60, error_on_exceed=True)
    
    limiter.wait()  # 第一次调用
    
    # 第二次调用应该抛出异常
    with pytest.raises(RateLimitExceededError) as exc_info:
        limiter.wait()
    
    assert exc_info.value.wait_time == pytest.approx(0.8, rel=1e-2)

@pytest.mark.asyncio
@patch('time.time')
@patch('asyncio.sleep')
async def test_async_wait(mock_sleep, mock_time):
    """测试异步等待。"""
    mock_time.side_effect = [1000.0, 1000.2, 1000.2]
    limiter = RateLimiter(calls_per_minute=60)
    
    await limiter.async_wait()  # 第一次调用
    mock_time.side_effect = [1000.2, 1000.2, 1000.2]
    await limiter.async_wait()  # 第二次调用
    
    # 验证异步等待
    mock_sleep.assert_called_once_with(0.8)
    assert limiter.stats["total_calls"] == 2

def test_context_manager():
    """测试上下文管理器。"""
    limiter = RateLimiter(calls_per_minute=60)
    
    with limiter:
        assert limiter.stats["total_calls"] == 1
    
    with limiter:
        assert limiter.stats["total_calls"] == 2

@pytest.mark.asyncio
async def test_async_context_manager():
    """测试异步上下文管理器。"""
    limiter = RateLimiter(calls_per_minute=60)
    
    async with limiter:
        assert limiter.stats["total_calls"] == 1
    
    async with limiter:
        assert limiter.stats["total_calls"] == 2

@patch('time.time')
def test_stats_collection(mock_time):
    """测试统计信息收集。"""
    mock_time.return_value = 1000.0
    limiter = RateLimiter(calls_per_minute=60)
    
    # 第一次调用
    limiter.wait()
    
    # 0.8秒后第二次调用
    mock_time.side_effect = [1000.8, 1000.8, 1000.8]
    limiter.wait()
    
    # 检查统计信息
    stats = limiter.get_stats()
    assert stats["total_calls"] == 2
    assert stats["total_wait_time"] == 0.2
    assert stats["max_wait_time"] == 0.2
    assert stats["avg_wait_time"] == 0.1
    assert stats["calls_per_minute"] == 60

@patch('time.time')
def test_stats_reset(mock_time):
    """测试统计信息重置。"""
    mock_time.return_value = 1000.0
    limiter = RateLimiter(calls_per_minute=60)
    
    # 进行一些调用
    limiter.wait()
    mock_time.return_value = 1000.5
    limiter.wait()
    
    # 检查初始统计
    stats = limiter.get_stats()
    assert stats["total_calls"] == 2
    
    # 模拟一小时后
    mock_time.return_value = 5000.0  # 超过1小时
    limiter.wait()
    
    # 检查统计是否重置
    stats = limiter.get_stats()
    assert stats["total_calls"] == 1
    assert stats["total_wait_time"] == 0
    assert stats["max_wait_time"] == 0

def test_thread_safety():
    """测试线程安全性。"""
    import threading
    
    limiter = RateLimiter(calls_per_minute=60)
    call_count = 0
    thread_count = 10
    calls_per_thread = 5
    
    def worker():
        nonlocal call_count
        for _ in range(calls_per_thread):
            with limiter:
                nonlocal call_count
                call_count += 1
    
    # 创建多个线程同时调用
    threads = [
        threading.Thread(target=worker)
        for _ in range(thread_count)
    ]
    
    # 启动所有线程
    for t in threads:
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    # 验证调用次数
    assert call_count == thread_count * calls_per_thread
    assert limiter.stats["total_calls"] == thread_count * calls_per_thread

@pytest.mark.asyncio
async def test_concurrent_async_calls():
    """测试并发异步调用。"""
    limiter = RateLimiter(calls_per_minute=60)
    
    async def worker():
        async with limiter:
            await asyncio.sleep(0.1)
    
    # 创建多个并发任务
    tasks = [worker() for _ in range(5)]
    await asyncio.gather(*tasks)
    
    # 验证调用次数
    assert limiter.stats["total_calls"] == 5

def test_error_message():
    """测试错误消息格式。"""
    error = RateLimitExceededError(1.5)
    assert "需要等待 1.50 秒" in str(error)

@patch('time.time')
def test_zero_wait_time(mock_time):
    """测试无需等待的边界情况。"""
    mock_time.return_value = 1000.0
    limiter = RateLimiter(calls_per_minute=60)
    
    limiter.wait()
    mock_time.return_value = 1002.0  # 2秒后，远超等待时间
    limiter.wait()
    
    assert limiter.stats["total_wait_time"] == 0
    assert limiter.stats["max_wait_time"] == 0 