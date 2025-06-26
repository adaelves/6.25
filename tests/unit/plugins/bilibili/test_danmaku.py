"""B站弹幕处理器测试模块。"""

import os
import time
import pytest
import requests
from pathlib import Path
from unittest.mock import Mock, patch
from xml.etree import ElementTree as ET
from .test_utils import generate_danmaku

from src.plugins.bilibili.danmaku import (
    download_danmaku,
    parse_danmaku,
    format_time,
    DanmakuError
)

class TestDanmaku:
    """弹幕处理器测试类。"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, tmp_path):
        """测试前置和后置操作。
        
        Args:
            tmp_path: pytest提供的临时目录路径
        """
        self.temp_dir = tmp_path
        self.test_xml_path = self.temp_dir / "test_danmaku.xml"
        
        # 测试用弹幕数据
        self.test_danmaku_xml = """<?xml version="1.0" encoding="UTF-8"?>
<i>
    <chatserver>chat.bilibili.com</chatserver>
    <chatid>12345678</chatid>
    <mission>0</mission>
    <maxlimit>1000</maxlimit>
    <d p="23.826000,1,25,16777215,1701234567,0,abcd1234,12345678">测试弹幕1</d>
    <d p="24.826000,4,25,16777215,1701234568,0,abcd1235,12345679">测试弹幕2</d>
    <d p="25.826000,5,25,16777215,1701234569,0,abcd1236,12345680">测试弹幕3</d>
</i>"""
        
        yield
        
        # 清理测试文件
        if self.test_xml_path.exists():
            self.test_xml_path.unlink()
            
    def test_download_danmaku_success(self, mocker):
        """测试成功下载弹幕。"""
        # Mock请求
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.test_danmaku_xml
        mock_response.raise_for_status = Mock()
        
        mocker.patch("requests.get", return_value=mock_response)
        
        # 执行下载
        result = download_danmaku("12345678", self.test_xml_path)
        
        assert result is True, "下载应该成功"
        assert self.test_xml_path.exists(), "应该生成XML文件"
        
        # 验证文件内容
        content = self.test_xml_path.read_text(encoding="utf-8")
        assert "测试弹幕1" in content, "应该包含弹幕文本"
        assert "23.826000,1,25" in content, "应该包含弹幕属性"
        
    def test_download_danmaku_network_error(self, mocker):
        """测试网络错误。"""
        mocker.patch(
            "requests.get",
            side_effect=requests.RequestException("网络错误")
        )
        
        result = download_danmaku("12345678", self.test_xml_path)
        assert result is False, "网络错误时应该返回False"
        assert not self.test_xml_path.exists(), "不应该生成文件"
        
    def test_download_danmaku_invalid_xml(self, mocker):
        """测试无效XML。"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Invalid XML"
        mock_response.raise_for_status = Mock()
        
        mocker.patch("requests.get", return_value=mock_response)
        
        result = download_danmaku("12345678", self.test_xml_path)
        assert result is False, "无效XML时应该返回False"
        
    def test_parse_danmaku(self):
        """测试弹幕解析。"""
        # 创建测试文件
        self.test_xml_path.write_text(self.test_danmaku_xml, encoding="utf-8")
        
        # 解析弹幕
        danmakus = parse_danmaku(self.test_xml_path)
        
        assert len(danmakus) == 3, "应该解析出3条弹幕"
        
        # 验证第一条弹幕
        first = danmakus[0]
        assert first["time"] == 23.826, "时间解析错误"
        assert first["type"] == "滚动弹幕", "类型解析错误"
        assert first["size"] == 25, "字体大小解析错误"
        assert first["color"] == "#ffffff", "颜色解析错误"
        assert first["text"] == "测试弹幕1", "文本解析错误"
        
    def test_parse_danmaku_invalid_file(self):
        """测试解析无效文件。"""
        # 创建无效XML文件
        self.test_xml_path.write_text("Invalid XML", encoding="utf-8")
        
        with pytest.raises(DanmakuError) as exc_info:
            parse_danmaku(self.test_xml_path)
            
        assert "弹幕解析失败" in str(exc_info.value)
        
    def test_parse_danmaku_missing_file(self):
        """测试解析不存在的文件。"""
        with pytest.raises(DanmakuError) as exc_info:
            parse_danmaku(Path("not_exists.xml"))
            
        assert "弹幕解析失败" in str(exc_info.value)
        
    @pytest.mark.parametrize("seconds,expected", [
        (0, "00:00.000"),
        (1.5, "00:01.500"),
        (61.001, "01:01.001"),
        (3600, "60:00.000"),
    ])
    def test_format_time(self, seconds, expected):
        """测试时间格式化。
        
        Args:
            seconds: 输入秒数
            expected: 期望的格式化结果
        """
        assert format_time(seconds) == expected
        
    def test_danmaku_types(self, mocker):
        """测试不同类型的弹幕。"""
        # 创建包含所有类型弹幕的XML
        test_xml = """<?xml version="1.0" encoding="UTF-8"?>
<i>
    <chatserver>chat.bilibili.com</chatserver>
    <mission>0</mission>
    <maxlimit>1000</maxlimit>
"""
        # 添加各种类型的弹幕
        for type_code, type_name in {1: "滚动弹幕", 4: "底部弹幕", 5: "顶部弹幕"}.items():
            test_xml += f'    <d p="0.000000,{type_code},25,16777215,1701234567,0,abcd1234,12345678">{type_name}</d>\n'
        test_xml += "</i>"
        
        # Mock请求
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = test_xml
        mock_response.raise_for_status = Mock()
        
        mocker.patch("requests.get", return_value=mock_response)
        
        # 下载并解析
        result = download_danmaku("12345678", self.test_xml_path)
        assert result is True, "下载应该成功"
        
        danmakus = parse_danmaku(self.test_xml_path)
        assert len(danmakus) == 3, "应该有3种类型的弹幕"
        
        types = {d["type"] for d in danmakus}
        assert types == {"滚动弹幕", "底部弹幕", "顶部弹幕"}, "应该包含所有基本类型"
        
    def test_concurrent_downloads(self, mocker):
        """测试并发下载。"""
        from concurrent.futures import ThreadPoolExecutor
        import random
        
        # Mock请求，模拟不同的延迟
        def delayed_response(*args, **kwargs):
            time.sleep(random.uniform(0.01, 0.05))
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = self.test_danmaku_xml
            mock_response.raise_for_status = Mock()
            return mock_response
            
        mocker.patch("requests.get", side_effect=delayed_response)
        
        # 并发下载多个弹幕文件
        paths = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            for i in range(5):
                save_path = self.temp_dir / f"danmaku_{i}.xml"
                paths.append(save_path)
                executor.submit(download_danmaku, "12345678", save_path)
                
        # 验证所有文件都下载成功
        assert all(path.exists() for path in paths), "所有文件都应该下载成功"
        
    def test_large_danmaku_file(self, mocker):
        """测试大量弹幕的处理。"""
        # 创建包含1000条弹幕的XML
        large_xml = """<?xml version="1.0" encoding="UTF-8"?>
<i>
    <chatserver>chat.bilibili.com</chatserver>
    <mission>0</mission>
    <maxlimit>1000</maxlimit>
"""
        for i in range(1000):
            large_xml += f'    <d p="{i}.000000,1,25,16777215,1701234567,0,abcd1234,{i}">弹幕{i}</d>\n'
        large_xml += "</i>"
        
        # Mock请求
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = large_xml
        mock_response.raise_for_status = Mock()
        
        mocker.patch("requests.get", return_value=mock_response)
        
        # 下载并解析
        result = download_danmaku("12345678", self.test_xml_path)
        assert result is True, "下载应该成功"
        
        danmakus = parse_danmaku(self.test_xml_path)
        assert len(danmakus) == 1000, "应该解析出1000条弹幕"
        assert danmakus[-1]["time"] == 999.0, "最后一条弹幕时间应该是999秒"

def test_danmaku_xml():
    """测试弹幕XML格式有效性。"""
    # 生成测试弹幕
    xml = generate_danmaku([
        (0, "test", "red"),
        (1.5, "测试", "blue"),
        (3.0, "こんにちは", "green")
    ])
    
    # 解析XML
    root = ET.fromstring(xml)
    
    # 验证基本结构
    assert root.tag == "i", "根节点标签应为'i'"
    assert len(root.findall("d")) == 3, "应包含3条弹幕"
    
    # 验证元数据
    assert root.find("chatserver").text == "chat.bilibili.com"
    assert root.find("mission").text == "0"
    assert root.find("maxlimit").text == "3"
    
    # 验证第一条弹幕
    first_danmaku = root.findall("d")[0]
    assert first_danmaku.text == "test"
    
    # 解析属性
    attrs = first_danmaku.get("p").split(",")
    assert len(attrs) == 8, "弹幕属性应包含8个字段"
    assert float(attrs[0]) == 0.0, "时间应为0.0"
    assert attrs[1] == "1", "类型应为1(滚动弹幕)"
    assert attrs[2] == "25", "字号应为25"
    assert attrs[3] == "16711680", "颜色应为红色(16711680)"
    
def test_danmaku_xml_empty():
    """测试空弹幕列表。"""
    xml = generate_danmaku([])
    root = ET.fromstring(xml)
    
    assert root.tag == "i"
    assert len(root.findall("d")) == 0
    assert root.find("maxlimit").text == "0"
    
@pytest.mark.parametrize("time_sec,text,color,expected_color", [
    (0, "test", "white", "16777215"),
    (0, "test", "red", "16711680"),
    (0, "test", "blue", "255"),
    (0, "test", "green", "65280"),
    (0, "test", "yellow", "16776960"),
    (0, "test", 12345, "12345"),  # 自定义颜色值
    (0, "test", "invalid", "16777215"),  # 无效颜色名称
])
def test_danmaku_colors(time_sec, text, color, expected_color):
    """测试弹幕颜色处理。"""
    xml = generate_danmaku([(time_sec, text, color)])
    root = ET.fromstring(xml)
    danmaku = root.find("d")
    
    color_value = danmaku.get("p").split(",")[3]
    assert color_value == expected_color
    
@pytest.mark.parametrize("time_sec", [
    0,
    0.5,
    1.234,
    999.999
])
def test_danmaku_time_format(time_sec):
    """测试弹幕时间格式。"""
    xml = generate_danmaku([(time_sec, "test", "white")])
    root = ET.fromstring(xml)
    danmaku = root.find("d")
    
    time_value = float(danmaku.get("p").split(",")[0])
    assert abs(time_value - time_sec) < 0.001
    
def test_danmaku_unicode():
    """测试Unicode字符支持。"""
    texts = [
        "你好世界",  # 中文
        "こんにちは",  # 日文
        "안녕하세요",  # 韩文
        "Hello, 世界!",  # 混合
        "🌟🎮🎵"  # Emoji
    ]
    
    xml = generate_danmaku([
        (i, text, "white") for i, text in enumerate(texts)
    ])
    root = ET.fromstring(xml)
    
    for i, danmaku in enumerate(root.findall("d")):
        assert danmaku.text == texts[i]
        
def test_danmaku_attributes():
    """测试弹幕属性完整性。"""
    xml = generate_danmaku([(0, "test", "white")])
    root = ET.fromstring(xml)
    danmaku = root.find("d")
    
    attrs = danmaku.get("p").split(",")
    assert len(attrs) == 8, "应包含8个属性字段"
    
    # 验证每个字段的类型
    assert float(attrs[0]) >= 0  # 时间
    assert attrs[1].isdigit()    # 类型
    assert attrs[2].isdigit()    # 字号
    assert attrs[3].isdigit()    # 颜色
    assert attrs[4].isdigit()    # 时间戳
    assert attrs[5].isdigit()    # 弹幕池
    assert attrs[6].isdigit()    # 用户ID
    assert attrs[7].isdigit()    # 弹幕ID 