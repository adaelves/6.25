"""B站API签名模块。

该模块实现B站API请求所需的签名生成功能。
参考：https://github.com/SocialSisterYi/bilibili-API-collect
"""

import time
import json
import logging
import zlib
from typing import Dict, Any, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

def calculate_w_rid(params: Dict[str, Any], wts: int) -> str:
    """计算w_rid签名。
    
    Args:
        params: 请求参数字典
        wts: 时间戳
        
    Returns:
        str: w_rid签名值
    """
    # 将参数按键排序
    sorted_params = dict(sorted(params.items()))
    
    # 构造签名字符串
    param_str = urlencode(sorted_params)
    sign_str = f"{param_str}&wts={wts}"
    
    # 计算CRC32
    w_rid = format(zlib.crc32(sign_str.encode()) & 0xFFFFFFFF, '08x')
    return w_rid

def generate_sign(params: Dict[str, Any], sessdata: Optional[str] = None) -> Dict[str, Any]:
    """生成带签名的请求参数。
    
    Args:
        params: 原始请求参数
        sessdata: 可选的SESSDATA值，用于认证
        
    Returns:
        Dict[str, Any]: 包含签名的完整参数
        
    Example:
        >>> params = {'aid': '12345', 'cid': '67890'}
        >>> signed_params = generate_sign(params, sessdata='your_sessdata')
        >>> print(signed_params)
        {
            'aid': '12345',
            'cid': '67890',
            'wts': '1624240000',
            'w_rid': 'abcd1234'
        }
    """
    try:
        # 复制原始参数
        signed_params = params.copy()
        
        # 添加时间戳
        wts = int(time.time())
        signed_params['wts'] = str(wts)
        
        # 如果提供了SESSDATA，添加到参数中
        if sessdata:
            signed_params['sessdata'] = sessdata
            
        # 计算w_rid
        w_rid = calculate_w_rid(signed_params, wts)
        signed_params['w_rid'] = w_rid
        
        # 移除sessdata（不需要发送）
        if 'sessdata' in signed_params:
            del signed_params['sessdata']
            
        logger.debug(f"生成签名参数: {json.dumps(signed_params, ensure_ascii=False)}")
        return signed_params
        
    except Exception as e:
        logger.error(f"生成签名失败: {e}")
        raise

def verify_sign(params: Dict[str, Any]) -> bool:
    """验证签名是否有效。
    
    Args:
        params: 包含签名的参数字典
        
    Returns:
        bool: 签名是否有效
    """
    try:
        # 提取签名相关参数
        w_rid = params.get('w_rid')
        wts = params.get('wts')
        if not w_rid or not wts:
            return False
            
        # 复制参数并移除签名
        verify_params = params.copy()
        del verify_params['w_rid']
        
        # 重新计算签名
        calculated_w_rid = calculate_w_rid(verify_params, int(wts))
        
        # 比较签名
        return w_rid == calculated_w_rid
        
    except Exception as e:
        logger.error(f"验证签名失败: {e}")
        return False 