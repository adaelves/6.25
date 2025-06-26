"""B站签名测试模块。

测试签名生成和验证功能。
"""

import time
import pytest
from src.plugins.bilibili.sign import generate_sign

def test_sign_expiry():
    """测试签名时效性。"""
    # 准备测试参数
    params = {
        "aid": "114514",
        "bvid": "BV1xx411c7mD",
        "cid": "12345678"
    }
    
    # 生成第一个签名
    old_sign = generate_sign(params)
    
    # 等待61秒(超过B站签名60秒有效期)
    time.sleep(61)
    
    # 生成新签名
    new_sign = generate_sign(params)
    
    # 验证签名不同
    assert old_sign != new_sign, "超过有效期后签名应该不同"
    
@pytest.mark.parametrize("params", [
    {"aid": "114514"},
    {"bvid": "BV1xx411c7mD"},
    {"aid": "114514", "bvid": "BV1xx411c7mD"},
    {"aid": "114514", "bvid": "BV1xx411c7mD", "cid": "12345678"}
])
def test_sign_consistency(params):
    """测试相同参数的签名一致性。"""
    # 连续生成两个签名(间隔很短)
    sign1 = generate_sign(params)
    sign2 = generate_sign(params)
    
    # 验证签名相同
    assert sign1 == sign2, "短时间内相同参数应生成相同签名"
    
def test_sign_parameter_order():
    """测试参数顺序对签名的影响。"""
    params1 = {
        "aid": "114514",
        "bvid": "BV1xx411c7mD",
        "cid": "12345678"
    }
    
    params2 = {
        "bvid": "BV1xx411c7mD",
        "cid": "12345678",
        "aid": "114514"
    }
    
    sign1 = generate_sign(params1)
    sign2 = generate_sign(params2)
    
    assert sign1 == sign2, "参数顺序不同应生成相同签名"
    
def test_sign_empty_params():
    """测试空参数签名。"""
    sign = generate_sign({})
    assert sign, "空参数也应该生成有效签名"
    
@pytest.mark.parametrize("invalid_params", [
    None,
    "invalid",
    123,
    ["aid", "bvid"],
    {"aid": None},
    {"aid": b"114514"}
])
def test_sign_invalid_params(invalid_params):
    """测试无效参数签名。"""
    with pytest.raises(ValueError):
        generate_sign(invalid_params)
        
def test_sign_timestamp():
    """测试签名中的时间戳。"""
    params = {"aid": "114514"}
    
    # 记录当前时间
    start_time = int(time.time())
    
    # 生成签名
    signed_params = generate_sign(params)
    
    # 记录结束时间
    end_time = int(time.time())
    
    # 从签名参数中提取时间戳
    timestamp = int(signed_params['wts'])
    
    # 验证时间戳在合理范围内
    assert start_time <= timestamp <= end_time, \
        "签名中的时间戳应在生成期间内" 