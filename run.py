import os
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 运行主程序
if __name__ == "__main__":
    from src.main import main
    main() 