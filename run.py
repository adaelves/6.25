"""启动脚本"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 导入并运行主程序
from src.main import main
import asyncio

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0) 