"""Twitter反爬虫测试模块。

测试Cloudflare绕过和其他反爬虫机制。
"""

import pytest
import requests
from unittest.mock import Mock, patch
from src.plugins.twitter.anti_crawl import CloudflareBypass

@pytest.fixture
def bypass():
    """创建CloudflareBypass实例。"""
    return CloudflareBypass()

@pytest.fixture
def mock_session(mocker):
    """模拟requests.Session。"""
    session = Mock(spec=requests.Session)
    mocker.patch('src.plugins.twitter.anti_crawl.requests.Session', return_value=session)
    return session

def test_init(bypass):
    """测试初始化。"""
    assert bypass.user_agent is not None
    assert bypass.cookies == {}
    assert bypass.headers['User-Agent'] == bypass.user_agent

def test_get_cf_cookies_success(bypass, mock_session):
    """测试成功获取CF cookies。"""
    # 模拟响应
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.cookies = {'cf_clearance': 'test_cookie'}
    mock_session.get.return_value = mock_response

    cookies = bypass.get_cf_cookies('https://twitter.com')
    assert 'cf_clearance' in cookies
    assert cookies['cf_clearance'] == 'test_cookie'

def test_get_cf_cookies_429(bypass, mock_session):
    """测试429错误处理。"""
    # 模拟429响应
    mock_response = Mock()
    mock_response.status_code = 429
    mock_session.get.return_value = mock_response

    with pytest.raises(Exception, match='Rate limited'):
        bypass.get_cf_cookies('https://twitter.com')

def test_get_cf_cookies_retry(bypass, mock_session):
    """测试重试机制。"""
    # 模拟响应序列：429 -> 200
    responses = [
        Mock(status_code=429),
        Mock(status_code=200, cookies={'cf_clearance': 'test_cookie'})
    ]
    mock_session.get.side_effect = responses

    cookies = bypass.get_cf_cookies('https://twitter.com', max_retries=2)
    assert 'cf_clearance' in cookies
    assert cookies['cf_clearance'] == 'test_cookie'
    assert mock_session.get.call_count == 2

def test_get_cf_cookies_max_retries(bypass, mock_session):
    """测试达到最大重试次数。"""
    # 模拟持续429响应
    mock_response = Mock(status_code=429)
    mock_session.get.return_value = mock_response

    with pytest.raises(Exception, match='Max retries reached'):
        bypass.get_cf_cookies('https://twitter.com', max_retries=3)
    assert mock_session.get.call_count == 3

def test_verify_cookies_valid(bypass):
    """测试验证有效的cookies。"""
    cookies = {'cf_clearance': 'valid_cookie'}
    assert bypass.verify_cookies(cookies)

def test_verify_cookies_invalid(bypass):
    """测试验证无效的cookies。"""
    invalid_cookies = [
        {},
        {'other': 'cookie'},
        {'cf_clearance': ''},
        None
    ]
    for cookies in invalid_cookies:
        assert not bypass.verify_cookies(cookies)

def test_rotate_user_agent(bypass):
    """测试User-Agent轮换。"""
    original_ua = bypass.user_agent
    bypass.rotate_user_agent()
    assert bypass.user_agent != original_ua
    assert bypass.headers['User-Agent'] == bypass.user_agent

@pytest.mark.asyncio
async def test_async_get_cf_cookies(bypass, mock_session):
    """测试异步获取CF cookies。"""
    # 模拟异步响应
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.cookies = {'cf_clearance': 'async_cookie'}
    mock_session.get.return_value = mock_response

    cookies = await bypass.async_get_cf_cookies('https://twitter.com')
    assert 'cf_clearance' in cookies
    assert cookies['cf_clearance'] == 'async_cookie'

def test_handle_js_challenge(bypass, mock_session):
    """测试处理JS挑战。"""
    # 模拟包含JS挑战的响应
    challenge_response = Mock()
    challenge_response.status_code = 403
    challenge_response.text = 'challenge-form'
    
    success_response = Mock()
    success_response.status_code = 200
    success_response.cookies = {'cf_clearance': 'challenge_passed'}
    
    mock_session.get.side_effect = [challenge_response, success_response]

    cookies = bypass.get_cf_cookies('https://twitter.com')
    assert 'cf_clearance' in cookies
    assert cookies['cf_clearance'] == 'challenge_passed'
    assert mock_session.get.call_count == 2

def test_handle_captcha(bypass, mock_session):
    """测试处理验证码。"""
    # 模拟验证码响应
    captcha_response = Mock()
    captcha_response.status_code = 403
    captcha_response.text = 'captcha-form'
    mock_session.get.return_value = captcha_response

    with pytest.raises(Exception, match='Captcha detected'):
        bypass.get_cf_cookies('https://twitter.com')

def test_proxy_support(bypass, mock_session):
    """测试代理支持。"""
    proxy = 'http://127.0.0.1:7890'
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.cookies = {'cf_clearance': 'proxy_cookie'}
    mock_session.get.return_value = mock_response

    cookies = bypass.get_cf_cookies('https://twitter.com', proxy=proxy)
    assert 'cf_clearance' in cookies
    mock_session.get.assert_called_with(
        'https://twitter.com',
        headers=bypass.headers,
        proxies={'http': proxy, 'https': proxy},
        timeout=30
    ) 