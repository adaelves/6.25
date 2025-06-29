"""Twitter内容提取器。"""

import asyncio
from typing import Optional
from playwright.async_api import Page, TimeoutError
import logging

logger = logging.getLogger(__name__)

class TwitterExtractor:
    """Twitter内容提取器。"""
    
    # 敏感内容警告文本（多语言支持）
    SENSITIVE_WARNINGS = [
        "敏感内容警告",  # 中文
        "Sensitive content warning",  # 英文
        "警告：センシティブな内容",  # 日文
        "민감한 콘텐츠 경고",  # 韩文
    ]
    
    # 确认按钮文本（多语言支持）
    CONFIRM_BUTTONS = [
        "查看",  # 中文
        "View",  # 英文
        "表示",  # 日文
        "보기",  # 韩文
    ]
    
    @staticmethod
    async def handle_sensitive_content(
        page: Page,
        timeout: float = 10000  # 10秒超时
    ) -> Optional[str]:
        """处理Twitter敏感内容警告。
        
        使用Playwright自动检测并跳过敏感内容警告页面。
        支持多语言警告文本。
        
        Args:
            page: Playwright页面实例
            timeout: 等待超时时间（毫秒）
            
        Returns:
            Optional[str]: 如果存在敏感内容警告并成功处理，返回页面内容；否则返回None
            
        Raises:
            TimeoutError: 当等待超时时抛出
        """
        try:
            # 构建警告文本选择器
            warning_selector = ", ".join([
                f"text={warning}" for warning in TwitterExtractor.SENSITIVE_WARNINGS
            ])
            
            # 构建按钮选择器
            button_selector = ", ".join([
                f"button:has-text('{text}')" for text in TwitterExtractor.CONFIRM_BUTTONS
            ])
            
            # 等待警告文本出现
            warning = await page.wait_for_selector(
                warning_selector,
                timeout=timeout,
                state="visible"
            )
            
            if warning:
                logger.info("检测到敏感内容警告，尝试自动处理")
                
                # 等待并点击确认按钮
                button = await page.wait_for_selector(
                    button_selector,
                    timeout=timeout,
                    state="visible"
                )
                
                if button:
                    await button.click()
                    
                    # 等待页面加载完成
                    await page.wait_for_load_state(
                        'networkidle',
                        timeout=timeout
                    )
                    
                    # 再次检查是否还有警告（处理多层警告）
                    try:
                        warning = await page.wait_for_selector(
                            warning_selector,
                            timeout=1000,  # 快速检查
                            state="visible"
                        )
                        if warning:
                            # 递归处理
                            return await TwitterExtractor.handle_sensitive_content(
                                page,
                                timeout
                            )
                    except TimeoutError:
                        pass
                        
                    logger.info("敏感内容警告处理完成")
                    return await page.content()
                    
        except TimeoutError as e:
            logger.warning(f"等待敏感内容警告超时: {e}")
        except Exception as e:
            logger.error(f"处理敏感内容警告出错: {e}")
            
        return None
        
    @staticmethod
    async def is_sensitive_content(page: Page) -> bool:
        """检查页面是否包含敏感内容警告。
        
        Args:
            page: Playwright页面实例
            
        Returns:
            bool: 是否包含敏感内容警告
        """
        try:
            # 构建警告文本选择器
            warning_selector = ", ".join([
                f"text={warning}" for warning in TwitterExtractor.SENSITIVE_WARNINGS
            ])
            
            # 快速检查是否存在警告文本
            warning = await page.wait_for_selector(
                warning_selector,
                timeout=1000,  # 1秒快速检查
                state="visible"
            )
            return warning is not None
            
        except TimeoutError:
            return False
        except Exception as e:
            logger.error(f"检查敏感内容警告出错: {e}")
            return False 