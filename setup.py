from setuptools import setup, find_packages

setup(
    name="youtube-downloader",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "yt-dlp",
        "PyQt6",
        # 其他依赖项可以从 requirements.txt 中读取
    ],
    python_requires=">=3.10",
) 