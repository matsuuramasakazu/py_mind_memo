from setuptools import setup, find_packages

setup(
    name="py_mind_memo",
    version="0.3.0",
    author="matsuuramasakazu",
    author_email="matsuuramasakazu@outlook.jp",
    description="A lightweight and intuitive mindmap like tool built with tkinter.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/matsuuramasakazu/py_mind_memo",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[],
    entry_points={
        "console_scripts": [
            "py_mind_memo=py_mind_memo.main:main",
        ],
    },
)
