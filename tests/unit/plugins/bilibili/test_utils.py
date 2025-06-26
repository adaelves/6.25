"""B站测试工具模块。

提供测试用例所需的辅助函数。
"""

import time
from typing import List, Tuple, Union
from xml.etree import ElementTree as ET

def generate_danmaku(
    items: List[Tuple[float, str, Union[str, int]]]
) -> str:
    """生成测试用弹幕XML。
    
    Args:
        items: 弹幕列表，每项为(时间, 文本, 颜色)元组
        
    Returns:
        str: 生成的XML字符串
        
    Example:
        >>> generate_danmaku([(0, "test", "red")])
        '<?xml version="1.0" encoding="UTF-8"?><i>...'
    """
    # 创建XML根节点
    root = ET.Element("i")
    
    # 添加元数据
    chat_server = ET.SubElement(root, "chatserver")
    chat_server.text = "chat.bilibili.com"
    
    mission = ET.SubElement(root, "mission")
    mission.text = "0"
    
    max_limit = ET.SubElement(root, "maxlimit")
    max_limit.text = str(len(items))
    
    # 添加弹幕
    for time_sec, text, color in items:
        # 转换颜色值
        if isinstance(color, str):
            # 支持颜色名称
            color_map = {
                "white": 16777215,
                "red": 16711680,
                "blue": 255,
                "green": 65280,
                "yellow": 16776960
            }
            color_value = color_map.get(color.lower(), 16777215)
        else:
            color_value = int(color)
            
        # 构建属性字符串
        # 格式：时间,类型,字号,颜色,时间戳,弹幕池,用户ID,弹幕ID
        attrs = [
            f"{time_sec:.3f}",  # 出现时间
            "1",                 # 滚动弹幕
            "25",               # 字号
            str(color_value),   # 颜色
            str(int(time.time())), # 发送时间戳
            "0",                # 弹幕池
            "0",                # 用户ID
            "0"                 # 弹幕ID
        ]
        
        # 创建弹幕元素
        d = ET.SubElement(root, "d")
        d.set("p", ",".join(attrs))
        d.text = text
        
    # 生成XML字符串
    return ET.tostring(root, encoding="unicode", xml_declaration=True) 