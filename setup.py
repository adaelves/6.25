"""安装配置文件。"""

from setuptools import setup, find_packages

setup(
    name="twitter-video-extractor",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "playwright>=1.53.0",
        "pytest>=7.0.0",
        "pytest-playwright>=0.7.0",
        "aiohttp>=3.8.0",
        "beautifulsoup4>=4.9.0"
    ],
    python_requires=">=3.10"
) 