"""TikTok签名生成模块。

提供Android和Web端签名生成功能。
支持v1/v2版本API。
"""

import time
import json
import hmac
import random
import base64
import logging
import hashlib
from typing import Dict, Optional, Union, Any
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

class SignatureError(Exception):
    """签名生成错误。"""
    pass

class TikTokSignature:
    """TikTok签名生成器。
    
    支持Android和Web端签名生成。
    自动在两种方案间切换。
    
    Attributes:
        device_id: str, 设备ID
        iid: str, 安装ID
        openudid: str, OpenUDID
        version_code: str, APP版本号
        version_name: str, APP版本名
        _use_android: bool, 是否使用Android签名
        _failed_count: int, Android签名失败次数
    """
    
    # API版本
    API_V1 = "v1"
    API_V2 = "v2"
    
    # Android APP信息
    ANDROID_APP_INFO = {
        "version_code": "260105",
        "version_name": "26.1.5",
        "package": "com.ss.android.ugc.trill",
        "channel": "googleplay"
    }
    
    # Web端信息
    WEB_INFO = {
        "aid": "1988",
        "app_name": "tiktok_web",
        "channel": "tiktok_web",
        "version_code": "180800",
        "device_platform": "web"
    }
    
    def __init__(self):
        """初始化签名生成器。"""
        self.device_id = self._generate_device_id()
        self.iid = self._generate_install_id()
        self.openudid = self._generate_openudid()
        self.version_code = self.ANDROID_APP_INFO["version_code"]
        self.version_name = self.ANDROID_APP_INFO["version_name"]
        self._use_android = True
        self._failed_count = 0
        
    def _generate_device_id(self) -> str:
        """生成设备ID。
        
        Returns:
            str: 19位数字字符串
        """
        return str(random.randint(10**18, 10**19 - 1))
        
    def _generate_install_id(self) -> str:
        """生成安装ID。
        
        Returns:
            str: 19位数字字符串
        """
        return str(random.randint(10**18, 10**19 - 1))
        
    def _generate_openudid(self) -> str:
        """生成OpenUDID。
        
        Returns:
            str: 16位数字字符串
        """
        return str(random.randint(10**15, 10**16 - 1))
        
    def _get_android_params(self) -> Dict[str, str]:
        """获取Android端公共参数。
        
        Returns:
            Dict[str, str]: 参数字典
        """
        return {
            "device_id": self.device_id,
            "iid": self.iid,
            "openudid": self.openudid,
            "version_code": self.version_code,
            "version_name": self.version_name,
            "manifest_version_code": self.version_code,
            "update_version_code": self.version_code,
            "aid": "1233",
            "channel": self.ANDROID_APP_INFO["channel"],
            "app_name": self.ANDROID_APP_INFO["package"],
            "device_platform": "android",
            "device_type": "Pixel 4",
            "os_version": "10",
            "os_api": "29",
            "resolution": "1080*1920",
            "dpi": "480",
            "timezone_name": "Asia/Shanghai",
            "carrier_region": "CN",
            "sys_region": "CN",
            "region": "CN",
            "app_language": "zh",
            "language": "zh",
            "timezone_offset": "28800",
            "ac": "wifi",
            "mcc_mnc": "46000",
            "is_my_cn": "0",
            "fp": self._generate_fp()
        }
        
    def _get_web_params(self) -> Dict[str, str]:
        """获取Web端公共参数。
        
        Returns:
            Dict[str, str]: 参数字典
        """
        return {
            **self.WEB_INFO,
            "device_id": self.device_id,
            "region": "CN",
            "priority_region": "CN",
            "os": "web",
            "referer": "",
            "cookie_enabled": "true",
            "screen_width": "1920",
            "screen_height": "1080",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Mozilla",
            "browser_version": "5.0",
            "browser_online": "true",
            "timezone_name": "Asia/Shanghai"
        }
        
    def _generate_fp(self) -> str:
        """生成指纹。
        
        Returns:
            str: 32位MD5字符串
        """
        data = f"{self.device_id}{int(time.time())}"
        return hashlib.md5(data.encode()).hexdigest()
        
    def _android_sign_v1(self, params: Dict[str, Any]) -> str:
        """Android端v1版本签名。
        
        Args:
            params: 参数字典
            
        Returns:
            str: 签名字符串
            
        Raises:
            SignatureError: 签名失败
        """
        try:
            # 添加公共参数
            params = {
                **self._get_android_params(),
                **params,
                "_rticket": str(int(time.time() * 1000))
            }
            
            # 按key排序
            sorted_params = dict(sorted(params.items()))
            
            # 拼接参数
            query = urlencode(sorted_params)
            
            # 计算签名
            key = b"abc123def456" # 示例密钥
            signature = hmac.new(
                key,
                query.encode(),
                hashlib.sha1
            ).hexdigest()
            
            return signature
            
        except Exception as e:
            logger.error(f"Android v1签名失败: {e}")
            self._failed_count += 1
            raise SignatureError(f"Android v1签名失败: {e}")
            
    def _android_sign_v2(self, params: Dict[str, Any]) -> str:
        """Android端v2版本签名。
        
        Args:
            params: 参数字典
            
        Returns:
            str: 签名字符串
            
        Raises:
            SignatureError: 签名失败
        """
        try:
            # 添加公共参数
            params = {
                **self._get_android_params(),
                **params,
                "ts": str(int(time.time())),
                "nonce": self._generate_nonce()
            }
            
            # 按key排序
            sorted_params = dict(sorted(params.items()))
            
            # 拼接参数
            data = json.dumps(sorted_params, separators=(",", ":"))
            
            # 计算签名
            key = b"xyz789uvw456" # 示例密钥
            signature = base64.b64encode(
                hmac.new(
                    key,
                    data.encode(),
                    hashlib.sha256
                ).digest()
            ).decode()
            
            return signature
            
        except Exception as e:
            logger.error(f"Android v2签名失败: {e}")
            self._failed_count += 1
            raise SignatureError(f"Android v2签名失败: {e}")
            
    def _web_sign(self, params: Dict[str, Any]) -> str:
        """Web端签名。
        
        Args:
            params: 参数字典
            
        Returns:
            str: 签名字符串
            
        Raises:
            SignatureError: 签名失败
        """
        try:
            # 添加公共参数
            params = {
                **self._get_web_params(),
                **params,
                "_signature": self._generate_web_signature()
            }
            
            # 按key排序
            sorted_params = dict(sorted(params.items()))
            
            # 拼接参数
            query = urlencode(sorted_params)
            
            # 计算签名
            return hashlib.md5(query.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"Web签名失败: {e}")
            raise SignatureError(f"Web签名失败: {e}")
            
    def _generate_web_signature(self) -> str:
        """生成Web端签名。
        
        Returns:
            str: 签名字符串
        """
        # Web端签名算法
        timestamp = int(time.time())
        nonce = "".join(random.choices("0123456789abcdef", k=16))
        data = f"{timestamp}:{nonce}"
        return base64.b64encode(data.encode()).decode()
        
    def _generate_nonce(self) -> str:
        """生成随机字符串。
        
        Returns:
            str: 16位随机字符串
        """
        return "".join(random.choices("0123456789abcdef", k=16))
        
    def sign(self, params: Dict[str, Any], api_version: str = API_V2) -> str:
        """生成签名。
        
        自动在Android和Web端签名间切换。
        连续失败3次后切换到Web端。
        
        Args:
            params: 参数字典
            api_version: API版本
            
        Returns:
            str: 签名字符串
            
        Raises:
            SignatureError: 签名失败
        """
        # 检查是否需要切换到Web端
        if self._failed_count >= 3:
            self._use_android = False
            self._failed_count = 0
            logger.warning("切换到Web端签名")
            
        try:
            if self._use_android:
                if api_version == self.API_V1:
                    return self._android_sign_v1(params)
                else:
                    return self._android_sign_v2(params)
            else:
                return self._web_sign(params)
                
        except SignatureError:
            # Android端签名失败,尝试Web端
            if self._use_android:
                logger.info("Android端签名失败,尝试Web端")
                self._use_android = False
                return self._web_sign(params)
            raise 