"""TikTok签名生成测试模块。

测试签名生成的稳定性和正确性。
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from src.plugins.tiktok.signature import TikTokSignature, SignatureError

@pytest.fixture
def signature():
    """创建签名生成器实例。"""
    return TikTokSignature()

def test_device_id_format(signature):
    """测试设备ID格式。"""
    assert len(signature.device_id) == 19
    assert signature.device_id.isdigit()

def test_install_id_format(signature):
    """测试安装ID格式。"""
    assert len(signature.iid) == 19
    assert signature.iid.isdigit()

def test_openudid_format(signature):
    """测试OpenUDID格式。"""
    assert len(signature.openudid) == 16
    assert signature.openudid.isdigit()

def test_android_params(signature):
    """测试Android端参数。"""
    params = signature._get_android_params()
    
    assert params["device_id"] == signature.device_id
    assert params["iid"] == signature.iid
    assert params["openudid"] == signature.openudid
    assert params["version_code"] == signature.version_code
    assert params["version_name"] == signature.version_name
    assert len(params["fp"]) == 32

def test_web_params(signature):
    """测试Web端参数。"""
    params = signature._get_web_params()
    
    assert params["device_id"] == signature.device_id
    assert params["aid"] == signature.WEB_INFO["aid"]
    assert params["app_name"] == signature.WEB_INFO["app_name"]
    assert params["device_platform"] == signature.WEB_INFO["device_platform"]

def test_android_v1_signature(signature):
    """测试Android v1签名。"""
    params = {"test": "value"}
    sign = signature._android_sign_v1(params)
    
    assert isinstance(sign, str)
    assert len(sign) == 40  # SHA1哈希长度

def test_android_v2_signature(signature):
    """测试Android v2签名。"""
    params = {"test": "value"}
    sign = signature._android_sign_v2(params)
    
    assert isinstance(sign, str)
    # Base64编码的SHA256哈希
    assert len(sign) > 40

def test_web_signature(signature):
    """测试Web端签名。"""
    params = {"test": "value"}
    sign = signature._web_sign(params)
    
    assert isinstance(sign, str)
    assert len(sign) == 32  # MD5哈希长度

def test_signature_stability():
    """测试签名稳定性。
    
    连续生成100次签名,验证成功率。
    """
    signature = TikTokSignature()
    params = {"test": "value"}
    success = 0
    
    for _ in range(100):
        try:
            sign = signature.sign(params)
            assert isinstance(sign, str)
            assert len(sign) > 0
            success += 1
        except SignatureError:
            continue
            
    assert success >= 80  # 成功率≥80%

def test_auto_fallback():
    """测试自动降级到Web端。"""
    signature = TikTokSignature()
    params = {"test": "value"}
    
    # 模拟Android签名连续失败
    with patch.object(signature, "_android_sign_v2") as mock_android:
        mock_android.side_effect = SignatureError("测试错误")
        
        # 第一次调用
        sign1 = signature.sign(params)
        assert isinstance(sign1, str)
        assert len(sign1) == 32  # Web端MD5哈希
        
        # 第二次调用应该直接使用Web端
        sign2 = signature.sign(params)
        assert isinstance(sign2, str)
        assert len(sign2) == 32
        
        # 验证Android签名只被调用一次
        assert mock_android.call_count == 1

def test_proxy_switch_delay():
    """测试代理切换延迟。
    
    验证切换代理的延迟是否<200ms。
    """
    signature = TikTokSignature()
    params = {"test": "value"}
    
    # 记录开始时间
    start = time.time()
    
    # 模拟Android签名失败触发切换
    with patch.object(signature, "_android_sign_v2") as mock_android:
        mock_android.side_effect = SignatureError("测试错误")
        signature.sign(params)
        
    # 计算延迟
    delay = (time.time() - start) * 1000
    assert delay < 200  # 延迟<200ms

def test_api_version_selection(signature):
    """测试API版本选择。"""
    params = {"test": "value"}
    
    # 测试v1版本
    with patch.object(signature, "_android_sign_v1") as mock_v1:
        signature.sign(params, api_version=TikTokSignature.API_V1)
        assert mock_v1.called
        
    # 测试v2版本
    with patch.object(signature, "_android_sign_v2") as mock_v2:
        signature.sign(params, api_version=TikTokSignature.API_V2)
        assert mock_v2.called

def test_invalid_params(signature):
    """测试无效参数。"""
    invalid_params = [
        None,
        "",
        [],
        {"": ""},
        {"test": None}
    ]
    
    for params in invalid_params:
        with pytest.raises(SignatureError):
            signature.sign(params)

def test_concurrent_signatures():
    """测试并发签名。
    
    验证多线程环境下的稳定性。
    """
    import threading
    
    signature = TikTokSignature()
    params = {"test": "value"}
    results = []
    errors = []
    
    def worker():
        try:
            sign = signature.sign(params)
            results.append(sign)
        except Exception as e:
            errors.append(e)
            
    # 创建10个线程
    threads = []
    for _ in range(10):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
        
    # 等待所有线程完成
    for t in threads:
        t.join()
        
    assert len(errors) == 0  # 无错误发生
    assert len(results) == 10  # 所有签名都成功
    assert len(set(results)) == 10  # 签名都是唯一的 