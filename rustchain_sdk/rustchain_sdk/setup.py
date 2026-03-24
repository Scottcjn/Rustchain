# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="rustchain",
    version="0.2.0",
    description="Python SDK for RustChain nodes",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="RustChain Contributors",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.24.0",
        "ecdsa>=0.18.0",
    ],
    extras_require={
        "cli": ["rich>=13.0.0"],
    },
    entry_points={
        "console_scripts": [
            "rustchain=rustchain_sdk.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
