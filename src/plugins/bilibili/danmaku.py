"""B站弹幕处理模块。

该模块负责下载和处理B站视频弹幕。
支持滚动弹幕和固定弹幕。
"""

import re
import logging
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

# 弹幕类型映射
DANMAKU_TYPE_MAP = {
    1: "滚动弹幕",
    4: "底部弹幕",
    5: "顶部弹幕",
    6: "逆向弹幕",
    7: "高级弹幕",
    8: "代码弹幕"
}

# XML实体转义映射
XML_ENTITIES = {
    "'": "&apos;",
    '"': "&quot;",
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
    "\n": "&#10;",
    "\r": "&#13;"
}

class DanmakuError(Exception):
    """弹幕处理异常。"""
    pass

def sanitize_xml_text(text: str) -> str:
    """净化XML文本。
    
    转义特殊字符，防止XML注入。
    
    Args:
        text: 原始文本
        
    Returns:
        str: 净化后的文本
    """
    if not text:
        return ""
    return escape(text, entities=XML_ENTITIES)

def download_danmaku(cid: str, save_path: Path) -> bool:
    """通过视频CID下载弹幕。
    
    Args:
        cid: 视频CID
        save_path: 保存路径
        
    Returns:
        bool: 是否成功
        
    Raises:
        DanmakuError: 弹幕下载或解析失败
    """
    try:
        # 构建API URL
        url = f"https://comment.bilibili.com/{cid}.xml"
        
        # 发送请求
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            timeout=30
        )
        response.raise_for_status()
        
        # 验证XML格式
        if not response.text.startswith("<?xml"):
            raise DanmakuError("返回数据不是有效的XML格式")
            
        # 解析XML
        root = ET.fromstring(response.text)
        
        # 创建新的XML文档
        new_root = ET.Element("i")
        
        # 添加元数据
        chat_server = ET.SubElement(new_root, "chatserver")
        chat_server.text = "chat.bilibili.com"
        
        mission_list = ET.SubElement(new_root, "mission")
        mission_list.text = "0"
        
        max_limit = ET.SubElement(new_root, "maxlimit")
        max_limit.text = str(len(root.findall(".//d")))
        
        # 处理每条弹幕
        for danmaku in root.findall(".//d"):
            # 获取属性
            attr = danmaku.get("p", "").split(",")
            if len(attr) < 8:
                logger.warning(f"跳过无效弹幕: {danmaku.text}")
                continue
                
            # 提取属性
            try:
                appear_time = float(attr[0])  # 出现时间（秒）
                danmaku_type = int(attr[1])   # 弹幕类型
                font_size = int(attr[2])      # 字体大小
                color = int(attr[3])          # 颜色
                timestamp = int(attr[4])       # 发送时间戳
                pool = int(attr[5])           # 弹幕池
                user_hash = attr[6]           # 用户哈希
                row_id = attr[7]              # 弹幕ID
            except (ValueError, IndexError) as e:
                logger.warning(f"弹幕属性解析失败: {e}")
                continue
                
            # 过滤无效弹幕
            if danmaku_type not in DANMAKU_TYPE_MAP:
                continue
                
            # 净化弹幕文本
            safe_text = sanitize_xml_text(danmaku.text)
            if not safe_text:
                continue
                
            # 创建弹幕元素
            d = ET.SubElement(new_root, "d")
            d.set("p", f"{appear_time:.6f},{danmaku_type},{font_size},{color},{timestamp},{pool},{user_hash},{row_id}")
            d.text = safe_text
            
        # 保存到文件
        tree = ET.ElementTree(new_root)
        tree.write(save_path, encoding="utf-8", xml_declaration=True)
        
        return True
        
    except requests.RequestException as e:
        logger.error(f"弹幕下载失败: {e}")
        raise DanmakuError(f"弹幕下载失败: {e}")
    except ET.ParseError as e:
        logger.error(f"XML解析失败: {e}")
        raise DanmakuError(f"XML解析失败: {e}")
    except Exception as e:
        logger.error(f"弹幕处理失败: {e}")
        raise DanmakuError(f"弹幕处理失败: {e}")
        
def parse_danmaku(xml_path: Path) -> List[Dict]:
    """解析弹幕XML文件。
    
    Args:
        xml_path: XML文件路径
        
    Returns:
        List[Dict]: 弹幕列表
        
    Raises:
        DanmakuError: 解析失败
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        danmakus = []
        for d in root.findall(".//d"):
            attr = d.get("p", "").split(",")
            if len(attr) < 8:
                continue
                
            try:
                danmakus.append({
                    "time": float(attr[0]),
                    "type": DANMAKU_TYPE_MAP.get(int(attr[1]), "未知"),
                    "size": int(attr[2]),
                    "color": f"#{int(attr[3]):06x}",
                    "timestamp": int(attr[4]),
                    "text": sanitize_xml_text(d.text or "")
                })
            except (ValueError, IndexError) as e:
                logger.warning(f"弹幕属性解析失败: {e}")
                continue
            
        return sorted(danmakus, key=lambda x: x["time"])
        
    except Exception as e:
        raise DanmakuError(f"弹幕解析失败: {e}")
        
def format_time(seconds: float) -> str:
    """格式化时间。
    
    Args:
        seconds: 秒数
        
    Returns:
        str: 格式化后的时间字符串 (MM:SS.ms)
    """
    minutes = int(seconds // 60)
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:06.3f}" 